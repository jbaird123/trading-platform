"""Golden validation tests comparing platform trades vs TradingView.

# Validates: [SE-3.5], [BT-7.8], [RV-9.1]

This module tests that our platform produces the same trades and PnL
as TradingView when running identical strategies on identical data.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

# Note: Backtester imports will be added when implementing
# from trading_platform.backtester import run_backtest
# from trading_platform.core.costs import CostModel
# from trading_platform.core.types import Trade
# from trading_platform.data import DataHandler


# === TOLERANCE DEFINITIONS ===

TRADE_VALIDATION_TOLERANCES = {
    "entry_time": timedelta(minutes=0),  # Exact match required
    "exit_time": timedelta(minutes=0),  # Exact match required
    "entry_price": 0.0001,  # 1 pip for forex (0.01%)
    "exit_price": 0.0001,  # 1 pip for forex
    "trade_pnl": 0.50,  # $0.50 per trade
    "total_pnl": 1.00,  # $1.00 total
    "trade_count": 0,  # Must match exactly
}

EQUITY_CURVE_TOLERANCES = {
    "correlation": 0.999,  # r > 0.999
    "final_equity": 1.00,  # $1.00 difference
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


def align_trades(
    our_trades: list[dict],
    tv_trades: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aligns platform and TradingView trades for comparison.

    Matches trades by entry time and returns aligned DataFrames.

    Args:
        our_trades: List of platform trade dictionaries
        tv_trades: DataFrame of TradingView trades

    Returns:
        Tuple of (platform_df, tradingview_df) aligned by entry time
    """
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
    tv_df = tv_trades.sort_values("entry_time").reset_index(drop=True)

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
):
    """Validates that entry/exit times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    pytest.skip("Pending TradingView data export")


def test_ema_crossover_trade_pnl_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
):
    """Validates that PnL matches within tolerance.

    # Validates: [PM-5.6], [BT-7.8]
    """
    pytest.skip("Pending TradingView data export")


def test_ema_crossover_equity_curve_correlation(
    golden_strategy_config,
    tradingview_trades,
):
    """Validates that equity curves are highly correlated.

    # Validates: [PM-5.3], [RV-9.1]
    """
    pytest.skip("Pending TradingView data export")


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
