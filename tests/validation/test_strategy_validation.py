"""Golden validation tests comparing platform trades vs TradingView.

# Validates: [SE-3.5], [BT-7.8], [RV-9.1]

This module tests that our platform produces the same trades and PnL
as TradingView when running identical strategies on identical data.

IMPORTANT: All golden validation tests MUST use the utility functions from
golden_utils.py to ensure consistent data loading, filtering, and validation.

See: docs/GOLDEN_VALIDATION.md for the golden validation contract.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

# Golden validation utilities (ALWAYS use these for golden tests)
from tests.validation.golden_utils import (
    filter_platform_trades_to_validation_range,
)

# Note: Backtester imports will be added when implementing
# from trading_platform.backtester import run_backtest
# from trading_platform.core.costs import CostModel
# from trading_platform.core.types import Trade
# from trading_platform.data import DataHandler


# === TOLERANCE DEFINITIONS ===

TRADE_VALIDATION_TOLERANCES: dict[str, Any] = {
    "entry_time": timedelta(hours=0),  # Zero tolerance - exact match required
    "exit_time": timedelta(hours=0),  # Zero tolerance - exact match required
    "entry_price": 0.0,  # Zero tolerance - exact match required
    "exit_price": 0.0,  # Zero tolerance - exact match required
    "trade_pnl": 0.01,  # 1 cent tolerance for floating-point precision
    "total_pnl": 0.01,  # 1 cent tolerance for floating-point precision
    "trade_count": 0,  # Must match exactly
}

EQUITY_CURVE_TOLERANCES: dict[str, float] = {
    "correlation": 1.0,  # Perfect correlation required
    "final_equity": 0.01,  # 1 cent tolerance for floating-point precision
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
    """Runs backtest and returns platform trades filtered to validation range.

    This function handles the complete golden validation workflow:
    1. Loads strategy and REM configs
    2. Runs backtest on OHLCV data (already filtered to warmup → validation end)
    3. Filters trades to validation range by entry_time
    4. Excludes "end_of_data" forced exits

    NOTE: The OHLCV data passed in should already be filtered to the extended range
    (warmup_start → validation_end). Use load_and_validate_ohlcv() for this.

    Args:
        strategy_name: Name of strategy (e.g., "ema_crossover/20pip_stop")
        run_config: Run configuration dictionary
        ohlcv_data: OHLCV data (already filtered to extended range)
        date_range: Validation range dict with 'start' and 'end' keys
                    Used to filter trades to validation period

    Returns:
        List of trade dictionaries filtered to validation range

    See: docs/GOLDEN_VALIDATION.md for the golden validation contract
    """
    from pathlib import Path

    import yaml
    from trading_platform.backtester.orchestrator import run_backtest_from_config
    from trading_platform.core.config import RunConfig

    # Filter OHLCV data to extended range [warmup_start, validation_end]
    # Even though caller may pass full OHLCV, we must filter it
    if date_range:
        from datetime import timedelta

        end_date = pd.to_datetime(date_range["end"], utc=True) + timedelta(
            days=1, seconds=-1
        )
        # Use hardcoded warmup start (1 month before validation on 2023-01-01)
        warmup_start = pd.Timestamp("2022-12-01", tz="UTC")
        ohlcv_to_use = ohlcv_data[
            (ohlcv_data.index >= warmup_start) & (ohlcv_data.index <= end_date)
        ].copy()
    else:
        ohlcv_to_use = ohlcv_data

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

    # Override warmup_bars to 0 when using extended data
    # Since we already extended the data by 100 bars, we don't want
    # the backtester to skip additional bars
    if date_range:
        config_dict["warmup_bars"] = 0

    # Create RunConfig
    config = RunConfig.model_validate(config_dict)

    # Run backtest on extended data
    results = run_backtest_from_config(
        config=config, market_data=ohlcv_to_use, strategy_config=strategy_config
    )

    # Filter trades to validation range using utility function
    # This handles:
    # - Excluding "end_of_data" forced exits (TradingView doesn't close at end)
    # - Filtering by entry_time within validation range
    # - Converting Trade objects to dictionaries
    if date_range:
        trades_list = filter_platform_trades_to_validation_range(
            results["trades"], date_range
        )
    else:
        # No filtering, just convert and exclude end_of_data
        trades_list = [
            {
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "side": trade.side,
            }
            for trade in results["trades"]
            if trade.exit_reason != "end_of_data"
        ]

    return trades_list


def parse_tradingview_trades(
    tv_df: pd.DataFrame, validation_range: dict[str, str] | None = None
) -> pd.DataFrame:
    """Parses TradingView CSV format into trade objects.

    DEPRECATED: Use load_and_validate_tradingview_trades() from golden_utils.py instead.
    That function handles validation range filtering automatically.

    TradingView exports have 2 rows per trade (entry + exit).
    This function combines them into single trade rows.

    Args:
        tv_df: Raw TradingView CSV DataFrame
        validation_range: Optional dict with 'start' and 'end' keys for filtering

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
            # TradingView exports are already in UTC (validated by golden test fixtures)
            # and already use bar open times (matching our platform convention).
            # No timezone conversion or timestamp adjustment needed.
            entry_time = entry_row.get("Date/Time")
            exit_time = exit_row.get("Date/Time")

            if not pd.isna(entry_time) and isinstance(entry_time, str):
                entry_time = pd.to_datetime(entry_time, utc=True)
            if not pd.isna(exit_time) and isinstance(exit_time, str):
                exit_time = pd.to_datetime(exit_time, utc=True)

            # Filter by validation range if provided
            # IMPORTANT: TradingView exports contain MORE trades than validation range
            # We must filter to exact validation range to match platform trades
            if validation_range:
                start_date = pd.to_datetime(validation_range["start"], utc=True)
                end_date = pd.to_datetime(validation_range["end"], utc=True)

                if not (start_date <= entry_time <= end_date):
                    # Skip trades outside validation period
                    continue

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
    validation_range: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aligns platform and TradingView trades for comparison.

    Matches trades by entry time and returns aligned DataFrames.

    NOTE: Prefers using load_and_validate_tradingview_trades() from golden_utils.py
    which handles validation range filtering automatically.

    Args:
        our_trades: List of platform trade dictionaries (already filtered)
        tv_trades: Raw TradingView DataFrame (will be parsed and filtered)
        validation_range: Optional dict with 'start' and 'end' for filtering TV trades

    Returns:
        Tuple of (platform_df, tradingview_df) aligned by entry time
    """
    # Parse TradingView trades (with optional validation range filtering)
    tv_df = parse_tradingview_trades(tv_trades, validation_range)

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
        pnl_diff = abs(our_trade["pnl"] - tv_trade["pnl"])
        if pnl_diff > tolerances["trade_pnl"]:
            results["passed"] = False
            results["discrepancies"].append(
                {
                    "type": "pnl_mismatch",
                    "trade_index": idx,
                    "platform": our_trade["pnl"],
                    "tradingview": tv_trade["pnl"],
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
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Compare counts
    # Parse TradingView trades with validation range filtering
    # This filters to validation range AND excludes open trades
    tv_trades_df = parse_tradingview_trades(
        tradingview_trades, golden_metadata.get("date_range")
    )

    tv_trade_count = len(tv_trades_df)
    platform_trade_count = len(platform_trades)

    # Validate against metadata's validation_range_closed_trades count
    # This is the count of closed trades within the validation date range
    # (after warmup filtering)
    expected_closed_trades = golden_metadata.get(
        "validation_range_closed_trades",
        golden_metadata.get("closed_trades", golden_metadata.get("total_trades")),
    )

    assert platform_trade_count == tv_trade_count, (
        f"Trade count mismatch: Platform={platform_trade_count}, "
        f"TradingView={tv_trade_count} (closed trades in validation range only)"
    )

    assert platform_trade_count == expected_closed_trades, (
        f"Trade count vs metadata mismatch: Platform={platform_trade_count}, "
        f"Metadata validation_range_closed_trades={expected_closed_trades}"
    )


def test_ema_crossover_entry_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates that entry times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades (pass validation_range to ensure TV trades are filtered)
    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )

    # Compare entry times
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
                    "platform": platform_trade["entry_time"],
                    "tradingview": tv_trade["entry_time"],
                    "diff": entry_diff,
                }
            )

    if mismatches:
        print("\n=== Entry Time Mismatches ===")
        for mm in mismatches[:10]:  # Show first 10
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry time mismatches. "
        f"Entry times must match exactly (tolerance={time_tolerance})"
    )


def test_ema_crossover_exit_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates that exit times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades (pass validation_range to ensure TV trades are filtered)
    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )

    # Compare exit times
    tolerances = TRADE_VALIDATION_TOLERANCES
    time_tolerance = tolerances["exit_time"]  # Already a timedelta

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Check exit time
        exit_diff = abs(platform_trade["exit_time"] - tv_trade["exit_time"])
        if exit_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "platform": platform_trade["exit_time"],
                    "tradingview": tv_trade["exit_time"],
                    "diff": exit_diff,
                }
            )

    if mismatches:
        print("\n=== Exit Time Mismatches ===")
        for mm in mismatches[:10]:  # Show first 10
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} exit time mismatches. "
        f"Exit times must match exactly (tolerance={time_tolerance})"
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
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades (pass validation_range to ensure TV trades are filtered)
    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )

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
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    # Align trades (pass validation_range to ensure TV trades are filtered)
    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )

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


def test_ema_crossover_metadata_schema_validation(golden_metadata):
    """Validates baseline metadata conforms to schema.

    # Validates: [RV-9.6]
    """
    # This test validates that the baseline strategy metadata is valid
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

    # Should pass - metadata already loaded and validated by fixture
    jsonschema.validate(instance=golden_metadata, schema=schema)

    # Verify key baseline metadata fields
    assert golden_metadata["dataset_type"] == "strategy"
    assert "ema_crossover" in golden_metadata["strategy_name"].lower()
    assert "date_range" in golden_metadata
    assert "initial_capital" in golden_metadata


# === 20-PIP STOP LOSS VARIATION TESTS ===


def test_ema_crossover_20pip_stop_trade_count_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop variation produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    if "Signal" in tradingview_trades.columns:
        closed_trades = tradingview_trades[tradingview_trades["Signal"] != "Open"]
    else:
        closed_trades = tradingview_trades

    tv_trade_count = len(closed_trades) // 2
    platform_trade_count = len(platform_trades)

    expected_closed_trades = golden_metadata.get(
        "validation_range_closed_trades",
        golden_metadata.get("closed_trades", golden_metadata.get("total_trades")),
    )

    assert platform_trade_count == tv_trade_count, (
        f"Trade count mismatch: Platform={platform_trade_count}, "
        f"TradingView={tv_trade_count}"
    )

    assert platform_trade_count == expected_closed_trades, (
        f"Trade count vs metadata: Platform={platform_trade_count}, "
        f"Metadata={expected_closed_trades}"
    )


def test_ema_crossover_20pip_stop_entry_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop entry times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    tolerances = TRADE_VALIDATION_TOLERANCES
    time_tolerance = tolerances["entry_time"]

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        entry_diff = abs(platform_trade["entry_time"] - tv_trade["entry_time"])

        if entry_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "platform": platform_trade["entry_time"],
                    "tradingview": tv_trade["entry_time"],
                    "diff": entry_diff,
                }
            )

    if mismatches:
        print("\n=== Entry Time Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry time mismatches. "
        f"Entry times must match exactly (tolerance={time_tolerance})"
    )


def test_ema_crossover_20pip_stop_exit_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop exit times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    tolerances = TRADE_VALIDATION_TOLERANCES
    time_tolerance = tolerances["exit_time"]

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        exit_diff = abs(platform_trade["exit_time"] - tv_trade["exit_time"])

        if exit_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "platform": platform_trade["exit_time"],
                    "tradingview": tv_trade["exit_time"],
                    "diff": exit_diff,
                }
            )

    if mismatches:
        print("\n=== Exit Time Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} exit time mismatches. "
        f"Exit times must match exactly (tolerance={time_tolerance})"
    )


def test_ema_crossover_20pip_stop_trade_pnl_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop PnL matches within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3], [PM-5.6]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    results = compare_trade_sequences(platform_df, tv_df, TRADE_VALIDATION_TOLERANCES)

    assert results["passed"], (
        f"PnL comparison failed:\n"
        f"Discrepancies: {len(results['discrepancies'])}\n"
        f"Details: {results['discrepancies'][:5]}"
    )


def test_ema_crossover_20pip_stop_equity_curve_correlation(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop equity curves are highly correlated.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    initial_capital = golden_metadata.get("initial_capital", 100000.0)

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )

    platform_equity = [initial_capital]
    tv_equity = [initial_capital]

    for i in range(len(platform_df)):
        platform_equity.append(platform_equity[-1] + platform_df.iloc[i]["pnl"])
        tv_equity.append(tv_equity[-1] + tv_df.iloc[i]["pnl"])

    correlation = np.corrcoef(platform_equity, tv_equity)[0, 1]
    final_diff = abs(platform_equity[-1] - tv_equity[-1])

    print("\n=== 20-Pip Stop Equity Analysis ===")
    print(f"Platform final: ${platform_equity[-1]:,.2f}")
    print(f"TradingView final: ${tv_equity[-1]:,.2f}")
    print(f"Difference: ${final_diff:.2f}")
    print(f"Correlation: {correlation:.6f}")

    min_corr = EQUITY_CURVE_TOLERANCES["correlation"]
    max_diff = EQUITY_CURVE_TOLERANCES["final_equity"]

    assert correlation >= min_corr, f"Correlation {correlation:.6f} < {min_corr:.6f}"

    assert (
        final_diff <= max_diff
    ), f"Final equity diff ${final_diff:.2f} > ${max_diff:.2f}"


def test_ema_crossover_20pip_stop_metadata_schema_validation(golden_metadata):
    """Validates 20-pip stop metadata conforms to schema.

    # Validates: [RV-9.6]
    """
    # This test validates that the 20pip_stop strategy metadata is valid
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

    # Should pass - metadata already loaded and validated by fixture
    jsonschema.validate(instance=golden_metadata, schema=schema)

    # Verify key 20pip_stop metadata fields
    assert golden_metadata["dataset_type"] == "strategy"
    assert "ema_crossover" in golden_metadata["strategy_name"].lower()
    assert "20pip_stop" in golden_metadata["strategy_name"].lower()
    assert "date_range" in golden_metadata
    assert "initial_capital" in golden_metadata
