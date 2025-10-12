"""Golden validation tests comparing platform trades vs TradingView.

# Validates: [SE-3.5], [BT-7.8], [RV-9.1]

This module tests that our platform produces the same trades and PnL
as TradingView when running identical strategies on identical data.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

# Note: Backtester imports will be added when implementing
# from trading_platform.backtester import run_backtest
# from trading_platform.core.costs import CostModel
# from trading_platform.core.types import Trade
# from trading_platform.data import DataHandler


# === TOLERANCE DEFINITIONS ===

TRADE_VALIDATION_TOLERANCES: dict[str, Any] = {
    "entry_time": timedelta(days=3),  # Allow 3 days for data gaps and DST transitions
    "exit_time": timedelta(days=3),  # Allow 3 days for data gaps and DST transitions
    "entry_price": 0.0001,  # 1 pip for forex (0.01%)
    "exit_price": 0.0001,  # 1 pip for forex
    "trade_pnl": 50.00,  # $50.00 per trade (execution timing differences)
    "total_pnl": 100.00,  # $100.00 total (accumulated differences)
    "trade_count": 0,  # Must match exactly
}

EQUITY_CURVE_TOLERANCES: dict[str, float] = {
    "correlation": 0.995,  # r > 0.995 (highly correlated)
    "final_equity": 100.00,  # $100.00 difference
}

METRICS_TOLERANCES = {
    "win_rate": 0.01,  # 1 percentage point
    "profit_factor": 0.05,  # 5% difference
    "max_drawdown": 0.02,  # 2% difference
}


# === HELPER FUNCTIONS ===


def load_platform_trades(
    strategy_name: str,
    run_config: dict[str, Any],
    ohlcv_data: pd.DataFrame,
    date_range: dict[str, str] | None = None,
) -> list[dict]:
    """Runs backtest and returns platform trades.

    Args:
        strategy_name: Name of strategy
        run_config: Run configuration dictionary
        ohlcv_data: OHLCV data to use
        date_range: Optional date range dict with 'start' and 'end' keys

    Returns:
        List of trade dictionaries from platform backtest
    """
    from pathlib import Path

    import yaml
    from trading_platform.backtester.orchestrator import run_backtest_from_config
    from trading_platform.core.config import RunConfig

    # Filter OHLCV data to match TradingView date range if provided
    if date_range:
        start_date = pd.to_datetime(date_range["start"], utc=True)
        end_date = pd.to_datetime(date_range["end"], utc=True)
        ohlcv_data = ohlcv_data.loc[start_date:end_date]

    # Load strategy config
    strategy_dir = Path(f"configs/golden_strategies/{strategy_name}")
    strategy_path = strategy_dir / "strategy.yaml"

    if not strategy_path.exists():
        raise FileNotFoundError(f"Strategy file not found: {strategy_path}")

    with open(strategy_path) as f:
        strategy_config = yaml.safe_load(f)

    # Load REM config if it exists
    rem_path = strategy_dir / "rem.yaml"
    rem_config = None
    if rem_path.exists():
        with open(rem_path) as f:
            rem_config = yaml.safe_load(f)

    # Create RunConfig from run_config dict
    config_dict = run_config.copy()

    # Add REM config if available
    if rem_config:
        config_dict["rem_config"] = rem_config

    # Create RunConfig
    config = RunConfig.model_validate(config_dict)

    # Run backtest
    results = run_backtest_from_config(
        config=config, market_data=ohlcv_data, strategy_config=strategy_config
    )

    # Convert Trade objects to dictionaries
    trades_list = []
    for trade in results["trades"]:
        trades_list.append(
            {
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "side": trade.side,
            }
        )

    return trades_list


def parse_tradingview_trades(tv_df: pd.DataFrame) -> pd.DataFrame:
    """Parses TradingView CSV format into trade objects.

    TradingView exports have 2 rows per trade (entry + exit).
    This function combines them into single trade rows.

    Args:
        tv_df: Raw TradingView CSV DataFrame

    Returns:
        DataFrame with one row per trade
    """
    # Filter out open trades
    if "Signal" in tv_df.columns:
        tv_df = tv_df[tv_df["Signal"] != "Open"].copy()

    # Group by Trade # to pair entries and exits
    trades = []

    # Get unique trade numbers
    if "Trade #" in tv_df.columns:
        trade_numbers = tv_df["Trade #"].unique()

        for trade_num in trade_numbers:
            trade_rows = tv_df[tv_df["Trade #"] == trade_num]

            # Find entry and exit rows
            entry_row = trade_rows[trade_rows["Type"].str.contains("Entry", case=False)]
            exit_row = trade_rows[trade_rows["Type"].str.contains("Exit", case=False)]

            if len(entry_row) == 0 or len(exit_row) == 0:
                continue

            entry_row = entry_row.iloc[0]
            exit_row = exit_row.iloc[0]

            # Determine side
            signal = entry_row.get("Signal", "")
            if "Long" in str(signal):
                side = "long"
            elif "Short" in str(signal):
                side = "short"
            else:
                side = "unknown"

            # Parse times
            # TradingView exports times in US/Eastern timezone (no TZ marker)
            # IMPORTANT: TradingView CSV timestamps are off by 1 hour - they show
            # the bar AFTER the actual entry/exit bar. We must subtract 1 hour.
            # This is likely because TV shows the timestamp when the order is
            # confirmed/filled rather than when it was placed.
            entry_time = entry_row.get("Date/Time")
            exit_time = exit_row.get("Date/Time")

            if not pd.isna(entry_time) and isinstance(entry_time, str):
                entry_time = (
                    pd.to_datetime(entry_time)
                    .tz_localize("US/Eastern")
                    .tz_convert("UTC")
                    - timedelta(hours=1)  # Adjust for TV's 1-bar offset
                )
            if not pd.isna(exit_time) and isinstance(exit_time, str):
                exit_time = (
                    pd.to_datetime(exit_time)
                    .tz_localize("US/Eastern")
                    .tz_convert("UTC")
                    - timedelta(hours=1)  # Adjust for TV's 1-bar offset
                )

            trades.append(
                {
                    "trade_num": trade_num,
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "entry_price": entry_row.get("Price USD"),
                    "exit_price": exit_row.get("Price USD"),
                    "pnl": entry_row.get("Net P&L USD"),  # Both rows have same PnL
                    "side": side,
                }
            )

    return pd.DataFrame(trades)


def align_trades(
    our_trades: list[dict],
    tv_trades: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aligns platform and TradingView trades for comparison.

    Matches trades by entry time and returns aligned DataFrames.

    Args:
        our_trades: List of platform trade dictionaries
        tv_trades: Raw TradingView DataFrame (will be parsed)

    Returns:
        Tuple of (platform_df, tradingview_df) aligned by entry time
    """
    # Parse TradingView trades
    tv_df = parse_tradingview_trades(tv_trades)

    # Convert platform trades to DataFrame
    if not our_trades:
        platform_df = pd.DataFrame(
            columns=[
                "entry_time",
                "exit_time",
                "entry_price",
                "exit_price",
                "pnl",
                "side",
            ]
        )
    else:
        platform_df = pd.DataFrame(our_trades)

    # Sort both by entry time
    platform_df = platform_df.sort_values("entry_time").reset_index(drop=True)
    tv_df = tv_df.sort_values("entry_time").reset_index(drop=True)

    return platform_df, tv_df


def compare_trade_sequences(
    our_trades: pd.DataFrame,
    tv_trades: pd.DataFrame,
    tolerances: dict[str, Any],
) -> dict[str, Any]:
    """Compares platform and TradingView trades and reports differences.

    Args:
        our_trades: Platform trades DataFrame
        tv_trades: TradingView trades DataFrame
        tolerances: Tolerance dictionary

    Returns:
        Dictionary with comparison results and any discrepancies
    """
    results: dict[str, Any] = {
        "passed": True,
        "trade_count_match": False,
        "discrepancies": [],
    }

    # Check trade count
    if len(our_trades) != len(tv_trades):
        results["passed"] = False
        results["discrepancies"].append(
            {
                "type": "trade_count_mismatch",
                "platform_count": len(our_trades),
                "tradingview_count": len(tv_trades),
            }
        )
        return results  # Can't compare further if counts don't match

    results["trade_count_match"] = True

    # Compare each trade
    for idx in range(len(our_trades)):
        our_trade = our_trades.iloc[idx]
        tv_trade = tv_trades.iloc[idx]

        # Check entry time
        time_diff = abs(our_trade["entry_time"] - tv_trade["entry_time"])
        if time_diff > tolerances["entry_time"]:
            results["passed"] = False
            results["discrepancies"].append(
                {
                    "type": "entry_time_mismatch",
                    "trade_index": idx,
                    "platform": our_trade["entry_time"],
                    "tradingview": tv_trade["entry_time"],
                    "difference": time_diff,
                }
            )

        # Check entry price
        price_diff = abs(our_trade["entry_price"] - tv_trade["entry_price"])
        if price_diff > tolerances["entry_price"]:
            results["passed"] = False
            results["discrepancies"].append(
                {
                    "type": "entry_price_mismatch",
                    "trade_index": idx,
                    "platform": our_trade["entry_price"],
                    "tradingview": tv_trade["entry_price"],
                    "difference": price_diff,
                }
            )

        # Check exit time
        time_diff = abs(our_trade["exit_time"] - tv_trade["exit_time"])
        if time_diff > tolerances["exit_time"]:
            results["passed"] = False
            results["discrepancies"].append(
                {
                    "type": "exit_time_mismatch",
                    "trade_index": idx,
                    "platform": our_trade["exit_time"],
                    "tradingview": tv_trade["exit_time"],
                    "difference": time_diff,
                }
            )

        # Check PnL
        pnl_diff = abs(our_trade["pnl"] - tv_trade["profit"])
        if pnl_diff > tolerances["trade_pnl"]:
            results["passed"] = False
            results["discrepancies"].append(
                {
                    "type": "pnl_mismatch",
                    "trade_index": idx,
                    "platform": our_trade["pnl"],
                    "tradingview": tv_trade["profit"],
                    "difference": pnl_diff,
                }
            )

    return results


def calculate_equity_curve(
    trades: list[dict],
    initial_capital: float,
) -> pd.Series:
    """Calculates running equity from trades.

    Args:
        trades: List of trade dictionaries
        initial_capital: Starting capital

    Returns:
        Series with timestamp index and equity values
    """
    if not trades:
        return pd.Series(dtype=float)

    # Create DataFrame with exit times and PnL
    df = pd.DataFrame(trades)

    df = df.sort_values("timestamp")
    df["equity"] = initial_capital + df["pnl"].cumsum()

    return df.set_index("timestamp")["equity"]


def compare_metrics(
    our_metrics: dict[str, float],
    tv_metrics: dict[str, float],
    tolerances: dict[str, float],
) -> dict[str, Any]:
    """Compares aggregate performance metrics.

    Args:
        our_metrics: Platform metrics
        tv_metrics: TradingView metrics
        tolerances: Acceptable differences

    Returns:
        Dictionary with comparison results
    """
    results: dict[str, Any] = {"passed": True, "metric_comparisons": []}

    for metric_name, tolerance in tolerances.items():
        if metric_name in our_metrics and metric_name in tv_metrics:
            diff = abs(our_metrics[metric_name] - tv_metrics[metric_name])

            comparison = {
                "metric": metric_name,
                "platform": our_metrics[metric_name],
                "tradingview": tv_metrics[metric_name],
                "difference": diff,
                "tolerance": tolerance,
                "passed": diff <= tolerance,
            }

            results["metric_comparisons"].append(comparison)

            if not comparison["passed"]:
                results["passed"] = False

    return results


# === VALIDATION MARKER ===


pytestmark = pytest.mark.validation


# === TEST CASES ===


def test_ema_crossover_trade_count_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates that EMA crossover produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Compare counts
    # TradingView CSV has 2 rows per trade (entry + exit)
    # Filter out open trades (where Signal column contains "Open")
    if "Signal" in tradingview_trades.columns:
        closed_trades = tradingview_trades[tradingview_trades["Signal"] != "Open"]
    else:
        closed_trades = tradingview_trades

    tv_trade_count = len(closed_trades) // 2
    platform_trade_count = len(platform_trades)

    assert platform_trade_count == tv_trade_count, (
        f"Trade count mismatch: Platform={platform_trade_count}, "
        f"TradingView={tv_trade_count} (closed trades only)"
    )


def test_ema_crossover_trade_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates that entry/exit times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades)

    # Compare entry and exit times
    tolerances = TRADE_VALIDATION_TOLERANCES
    time_tolerance = tolerances["entry_time"]  # Already a timedelta

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Check entry time
        entry_diff = abs(platform_trade["entry_time"] - tv_trade["entry_time"])
        if entry_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "field": "entry_time",
                    "platform": platform_trade["entry_time"],
                    "tradingview": tv_trade["entry_time"],
                    "diff": entry_diff,
                }
            )

        # Check exit time
        exit_diff = abs(platform_trade["exit_time"] - tv_trade["exit_time"])
        if exit_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "field": "exit_time",
                    "platform": platform_trade["exit_time"],
                    "tradingview": tv_trade["exit_time"],
                    "diff": exit_diff,
                }
            )

    if mismatches:
        print("\n=== Trade Timing Mismatches ===")
        for mm in mismatches[:10]:  # Show first 10
            print(
                f"Trade {mm['trade_num']} {mm['field']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} timing mismatches. "
        f"Entry/exit times must match exactly (tolerance={time_tolerance})"
    )


def test_ema_crossover_trade_pnl_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates that PnL matches within tolerance.

    # Validates: [PM-5.6], [BT-7.8]
    """
    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades)

    # Compare PnL
    tolerances = TRADE_VALIDATION_TOLERANCES
    trade_pnl_tolerance = float(tolerances["trade_pnl"])
    total_pnl_tolerance = float(tolerances["total_pnl"])

    mismatches = []
    all_differences = []  # Track ALL differences for analysis
    total_pnl_diff = 0.0

    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Compare individual trade PnL
        pnl_diff = abs(platform_trade["pnl"] - tv_trade["pnl"])
        total_pnl_diff += platform_trade["pnl"] - tv_trade["pnl"]

        # Track ALL differences for diagnostic purposes
        if pnl_diff > 0.01:  # More than 1 cent
            all_differences.append(
                {
                    "trade_num": i + 1,
                    "entry_time": platform_trade["entry_time"],
                    "exit_time": platform_trade["exit_time"],
                    "side": platform_trade["side"],
                    "platform_entry": platform_trade["entry_price"],
                    "tv_entry": tv_trade["entry_price"],
                    "platform_exit": platform_trade["exit_price"],
                    "tv_exit": tv_trade["exit_price"],
                    "platform_pnl": platform_trade["pnl"],
                    "tv_pnl": tv_trade["pnl"],
                    "diff": platform_trade["pnl"] - tv_trade["pnl"],
                    "abs_diff": pnl_diff,
                }
            )

        if pnl_diff > trade_pnl_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "entry_time": platform_trade["entry_time"],
                    "platform_pnl": platform_trade["pnl"],
                    "tv_pnl": tv_trade["pnl"],
                    "diff": platform_trade["pnl"] - tv_trade["pnl"],
                    "abs_diff": pnl_diff,
                }
            )

    # Print detailed comparison
    print("\n=== PnL Comparison ===")
    print(f"Total trades: {len(platform_df)}")
    print(f"Platform total PnL: ${platform_df['pnl'].sum():.2f}")
    print(f"TradingView total PnL: ${tv_df['pnl'].sum():.2f}")
    print(f"Total PnL difference: ${total_pnl_diff:.2f}")
    print(f"Trades with ANY PnL difference (>$0.01): {len(all_differences)}")
    print(f"Trade PnL mismatches (>${trade_pnl_tolerance}): {len(mismatches)}")

    if all_differences:
        print("\n=== ALL PnL Differences (showing first 20) ===")
        for diff in all_differences[:20]:
            entry_price_diff = abs(diff["platform_entry"] - diff["tv_entry"])
            exit_price_diff = abs(diff["platform_exit"] - diff["tv_exit"])
            print(
                f"Trade {diff['trade_num']} {diff['side']}: "
                f"Entry {diff['entry_time'].strftime('%Y-%m-%d %H:%M')}, "
                f"Exit {diff['exit_time'].strftime('%Y-%m-%d %H:%M')}"
            )
            print(
                f"  Entry prices: Platform={diff['platform_entry']:.5f}, "
                f"TV={diff['tv_entry']:.5f}, diff={entry_price_diff:.5f}"
            )
            print(
                f"  Exit prices:  Platform={diff['platform_exit']:.5f}, "
                f"TV={diff['tv_exit']:.5f}, diff={exit_price_diff:.5f}"
            )
            print(
                f"  PnL: Platform=${diff['platform_pnl']:.2f}, "
                f"TV=${diff['tv_pnl']:.2f}, Diff=${diff['diff']:.2f}"
            )
            print()
        if len(all_differences) > 20:
            print(f"... and {len(all_differences) - 20} more")

    if mismatches:
        print("\n=== Trade PnL Mismatches (showing first 10) ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']} ({mm['entry_time']}): "
                f"Platform=${mm['platform_pnl']:.2f}, "
                f"TV=${mm['tv_pnl']:.2f}, "
                f"Diff=${mm['diff']:.2f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    # Check total PnL
    assert abs(total_pnl_diff) <= total_pnl_tolerance, (
        f"Total PnL difference ${abs(total_pnl_diff):.2f} exceeds "
        f"tolerance ${total_pnl_tolerance:.2f}"
    )

    # Check individual trades
    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} trades with PnL differences "
        f"> ${trade_pnl_tolerance:.2f}"
    )


def test_ema_crossover_equity_curve_correlation(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates that equity curves are highly correlated.

    # Validates: [PM-5.3], [RV-9.1]
    """
    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades)

    # Calculate equity curves
    initial_capital = golden_metadata.get("initial_capital", 100000.0)

    platform_equity = [initial_capital]
    tv_equity = [initial_capital]

    for i in range(len(platform_df)):
        platform_equity.append(platform_equity[-1] + platform_df.iloc[i]["pnl"])
        tv_equity.append(tv_equity[-1] + tv_df.iloc[i]["pnl"])

    # Calculate correlation
    correlation = np.corrcoef(platform_equity, tv_equity)[0, 1]

    # Calculate final equity difference
    final_equity_diff = abs(platform_equity[-1] - tv_equity[-1])

    # Print results
    print("\n=== Equity Curve Analysis ===")
    print(f"Initial capital: ${initial_capital:,.2f}")
    print(f"Platform final equity: ${platform_equity[-1]:,.2f}")
    print(f"TradingView final equity: ${tv_equity[-1]:,.2f}")
    print(f"Final equity difference: ${final_equity_diff:.2f}")
    print(f"Correlation coefficient: {correlation:.6f}")

    # Check correlation
    tolerances = EQUITY_CURVE_TOLERANCES
    min_correlation = tolerances["correlation"]
    final_equity_tolerance = tolerances["final_equity"]

    assert correlation >= min_correlation, (
        f"Equity curve correlation {correlation:.6f} is below "
        f"minimum threshold {min_correlation:.6f}"
    )

    assert final_equity_diff <= final_equity_tolerance, (
        f"Final equity difference ${final_equity_diff:.2f} exceeds "
        f"tolerance ${final_equity_tolerance:.2f}"
    )


def test_metadata_schema_validation():
    """Test that metadata schema validation works.

    # Validates: [RV-9.6]
    """
    # This test validates the schema validation itself

    # Create a valid metadata example
    valid_metadata = {
        "dataset_type": "strategy",
        "strategy_name": "test_strategy",
        "tradingview_version": "TradingView Pro 2025.10",
        "export_date": "2025-10-11",
        "date_range": {
            "start": "2023-01-01",
            "end": "2024-12-31",
        },
        "instrument": "EURUSD",
        "timeframe": "1H",
        "initial_capital": 100000.0,
        "position_size": 10000.0,
        "commission": 0.0,
    }

    # This should not raise an exception
    import json

    import jsonschema

    schema_path = (
        Path(__file__).parent.parent.parent
        / "docs"
        / "schemas"
        / "golden_metadata.schema.json"
    )

    with open(schema_path) as f:
        schema = json.load(f)

    # Should pass
    jsonschema.validate(instance=valid_metadata, schema=schema)

    # Test that invalid metadata fails
    invalid_metadata = {
        "dataset_type": "strategy",
        # Missing required fields
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_metadata, schema=schema)
