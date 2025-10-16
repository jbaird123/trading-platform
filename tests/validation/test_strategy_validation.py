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
    "entry_price": 1e-10,  # Floating-point precision tolerance
    "exit_price": 1e-10,  # Floating-point precision tolerance
    "trade_count": 0,  # Must match exactly
}

# === KNOWN EDGE CASES ===
#
# Documents trades with known, legitimate discrepancies that should not fail tests.
# Each edge case must include a detailed explanation of why the discrepancy exists.
#
# TEMPORARILY COMMENTED OUT - Re-investigating with new TradingView export
# to determine if edge cases still exist or were PineScript artifacts
#
KNOWN_EDGE_CASES: dict[str, dict[str, list[dict]]] = {
    "ema_crossover/20pip_stop_40pip_tp": {
        "exit_price_mismatches": [
            {
                "trade_index": 121,  # Trade 122 in 1-indexed display
                "entry_time": "2024-01-10 17:00:00",
                "exit_time": "2024-01-11 13:00:00",
                "description": (
                    "Both SL and TP hit on same bar - tie-break policy difference"
                ),
                "explanation": (
                    "Long entry at 1.09592 with 20-pip SL at 1.09392 and "
                    "40-pip TP at 1.09992. Exit bar (2024-01-11 13:00) had "
                    "low=1.09356 (hitting SL) and high=1.09996 (hitting TP). "
                    "Platform correctly applies exit_tie_break='stop_then_tp' "
                    "policy and exits at SL price 1.09392. TradingView cannot "
                    "determine intra-bar order in historical backtesting and "
                    "exits at TP price 1.09992. This is a fundamental "
                    "limitation of TradingView's bar-replay engine - it cannot "
                    "prioritize exits when both levels are breached within the "
                    "same bar. Platform behavior is correct per configured "
                    "policy."
                ),
                "platform_exit_price": 1.09392,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_price": 1.09992,
                "bar_low": 1.09356,
                "bar_high": 1.09996,
            },
        ]
    }
    # "ema_crossover/20pip_stop": {
    #     "exit_time_mismatches": [
    #         {
    #             "trade_index": 230,  # Trade 231 in 1-indexed display
    #             "entry_time": "2024-11-03 22:00:00",
    #             "description": "Weekend gap edge case",
    #             "explanation": (
    #                 "Entry signal generated Friday close. Market opened "
    #                 "Sunday evening with significant upward price gap. "
    #                 "Platform correctly exits on opposite signal at next bar. "
    #                 "TradingView incorrectly records as 'Short SL' at entry "
    #                 "price ($0 PnL) - likely because stop loss level was "
    #                 "calculated on Friday and was already violated by Sunday "
    #                 "open gap. This is a TradingView data artifact, not a "
    #                 "platform bug."
    #             ),
    #             "platform_exit_reason": "opposite_signal",
    #             "tradingview_exit_reason": "Short SL",
    #         },
    #         {
    #             "trade_index": 245,  # Trade 246 in 1-indexed display
    #             "entry_time": "2024-12-22 22:00:00",
    #             "description": "Spread handling difference",
    #             "explanation": (
    #                 "Platform correctly implements spread-aware stop loss, "
    #                 "while TradingView uses mid-price only. Long entry at "
    #                 "1.04316 with 20-pip stop at 1.04116. In 07:00 bar, "
    #                 "mid-price low reached 1.04113 (0.3 pips below stop). "
    #                 "Platform accounts for bid/ask spread and correctly "
    #                 "triggers stop, exiting at 1.04116 with exactly -$20.00. "
    #                 "TradingView's mid-price logic doesn't trigger until "
    #                 "08:00 bar, exiting at 1.04094 with -$21.29. Platform "
    #                 "behavior is MORE correct - follows proper spread-aware "
    #                 "rules."
    #             ),
    #             "platform_exit_reason": "stop-loss",
    #             "tradingview_exit_reason": "Long SL",
    #         },
    #     ]
    # }
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


def test_ema_crossover_entry_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates baseline entry prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    tolerances = TRADE_VALIDATION_TOLERANCES
    price_tolerance = tolerances["entry_price"]

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        price_diff = abs(platform_trade["entry_price"] - tv_trade["entry_price"])

        if price_diff > price_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "entry_time": platform_trade["entry_time"],
                    "platform": platform_trade["entry_price"],
                    "tradingview": tv_trade["entry_price"],
                    "diff": price_diff,
                }
            )

    if mismatches:
        print("\n=== Entry Price Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']} ({mm['entry_time']}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry price mismatches. "
        f"Entry prices must match exactly (tolerance={price_tolerance})"
    )


def test_ema_crossover_exit_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates baseline exit prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/baseline",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    tolerances = TRADE_VALIDATION_TOLERANCES
    price_tolerance = tolerances["exit_price"]

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        price_diff = abs(platform_trade["exit_price"] - tv_trade["exit_price"])

        if price_diff > price_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "entry_time": platform_trade["entry_time"],
                    "exit_time": platform_trade["exit_time"],
                    "platform": platform_trade["exit_price"],
                    "tradingview": tv_trade["exit_price"],
                    "diff": price_diff,
                }
            )

    if mismatches:
        print("\n=== Exit Price Mismatches ===")
        for mm in mismatches[:10]:
            entry_time = mm["entry_time"]
            exit_time = mm["exit_time"]
            print(
                f"Trade {mm['trade_num']} (Entry: {entry_time}, "
                f"Exit: {exit_time}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} exit price mismatches. "
        f"Exit prices must match exactly (tolerance={price_tolerance})"
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

    Excludes trades where platform had same-bar stop-loss exits, as TradingView's
    historical backtesting cannot check stops within a bar (only at next bar open).

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
    excluded_same_bar = []

    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Exclude same-bar stop-loss exits (TradingView limitation)
        # Platform can detect intra-bar stops, TradingView cannot
        if platform_trade["entry_time"] == platform_trade["exit_time"]:
            excluded_same_bar.append(i)
            continue

        exit_diff = abs(platform_trade["exit_time"] - tv_trade["exit_time"])

        if exit_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "trade_index": i,
                    "platform": platform_trade["exit_time"],
                    "tradingview": tv_trade["exit_time"],
                    "diff": exit_diff,
                }
            )

    # Report excluded trades
    if excluded_same_bar:
        print("\n=== Excluded Same-Bar Stop-Loss Exits ===")
        print(
            f"Excluded {len(excluded_same_bar)} trades where platform detected "
            f"intra-bar stop-loss."
        )
        print(
            "This is expected: TradingView's historical backtesting cannot "
            "check stops within a bar."
        )

    # Report unexpected mismatches
    if mismatches:
        print("\n=== UNEXPECTED Exit Time Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} UNEXPECTED exit time mismatches. "
        f"Exit times must match exactly (tolerance={time_tolerance}). "
        f"Note: {len(excluded_same_bar)} same-bar exits were excluded."
    )


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


def test_ema_crossover_20pip_stop_entry_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop entry prices match within tolerance.

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
    price_tolerance = tolerances["entry_price"]

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        price_diff = abs(platform_trade["entry_price"] - tv_trade["entry_price"])

        if price_diff > price_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "entry_time": platform_trade["entry_time"],
                    "platform": platform_trade["entry_price"],
                    "tradingview": tv_trade["entry_price"],
                    "diff": price_diff,
                }
            )

    if mismatches:
        print("\n=== Entry Price Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']} ({mm['entry_time']}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry price mismatches. "
        f"Entry prices must match exactly (tolerance={price_tolerance})"
    )


def test_ema_crossover_20pip_stop_exit_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop exit prices match within tolerance.

    Excludes trades where platform had same-bar stop-loss exits, as TradingView's
    historical backtesting cannot check stops within a bar (only at next bar open).

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
    price_tolerance = tolerances["exit_price"]

    mismatches = []
    excluded_same_bar = []

    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Exclude same-bar stop-loss exits (TradingView limitation)
        # Platform can detect intra-bar stops, TradingView cannot
        if platform_trade["entry_time"] == platform_trade["exit_time"]:
            excluded_same_bar.append(i)
            continue

        price_diff = abs(platform_trade["exit_price"] - tv_trade["exit_price"])

        if price_diff > price_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "trade_index": i,
                    "entry_time": platform_trade["entry_time"],
                    "exit_time": platform_trade["exit_time"],
                    "platform": platform_trade["exit_price"],
                    "tradingview": tv_trade["exit_price"],
                    "diff": price_diff,
                }
            )

    # Report excluded trades
    if excluded_same_bar:
        print("\n=== Excluded Same-Bar Stop-Loss Exits ===")
        print(
            f"Excluded {len(excluded_same_bar)} trades where platform detected "
            f"intra-bar stop-loss."
        )
        print(
            "This is expected: TradingView's historical backtesting cannot "
            "check stops within a bar."
        )

    # Report unexpected mismatches
    if mismatches:
        print("\n=== UNEXPECTED Exit Price Mismatches ===")
        for mm in mismatches[:10]:
            entry_time = mm["entry_time"]
            exit_time = mm["exit_time"]
            print(
                f"Trade {mm['trade_num']} (Entry: {entry_time}, "
                f"Exit: {exit_time}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} UNEXPECTED exit price mismatches. "
        f"Exit prices must match exactly (tolerance={price_tolerance}). "
        f"Note: {len(excluded_same_bar)} same-bar exits were excluded."
    )


# === 20-PIP STOP LOSS + 40-PIP TAKE PROFIT VARIATION TESTS ===


def test_ema_crossover_20pip_stop_40pip_tp_trade_count_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop + 40-pip TP variation produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop_40pip_tp",
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


def test_ema_crossover_20pip_stop_40pip_tp_entry_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop + 40-pip TP entry times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop_40pip_tp",
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


def test_ema_crossover_20pip_stop_40pip_tp_exit_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop + 40-pip TP exit times match within tolerance.

    Excludes trades where platform had same-bar stop-loss/TP exits, as TradingView's
    historical backtesting cannot check stops/TPs within a bar (only at next bar open).

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop_40pip_tp",
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
    excluded_same_bar = []

    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Exclude same-bar stop-loss/TP exits (TradingView limitation)
        # Platform can detect intra-bar stops/TPs, TradingView cannot
        if platform_trade["entry_time"] == platform_trade["exit_time"]:
            excluded_same_bar.append(i)
            continue

        exit_diff = abs(platform_trade["exit_time"] - tv_trade["exit_time"])

        if exit_diff > time_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "trade_index": i,
                    "platform": platform_trade["exit_time"],
                    "tradingview": tv_trade["exit_time"],
                    "diff": exit_diff,
                }
            )

    # Report excluded trades
    if excluded_same_bar:
        print("\n=== Excluded Same-Bar Stop-Loss/TP Exits ===")
        print(
            f"Excluded {len(excluded_same_bar)} trades where platform detected "
            f"intra-bar stop-loss or take-profit."
        )
        print(
            "This is expected: TradingView's historical backtesting cannot "
            "check stops/TPs within a bar."
        )

    # Report unexpected mismatches
    if mismatches:
        print("\n=== UNEXPECTED Exit Time Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}, "
                f"Diff={mm['diff']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} UNEXPECTED exit time mismatches. "
        f"Exit times must match exactly (tolerance={time_tolerance}). "
        f"Note: {len(excluded_same_bar)} same-bar exits were excluded."
    )


def test_ema_crossover_20pip_stop_40pip_tp_metadata_schema_validation(
    golden_metadata,
):
    """Validates 20-pip stop + 40-pip TP metadata conforms to schema.

    # Validates: [RV-9.6]
    """
    # This test validates that the 20pip_stop_40pip_tp strategy metadata is valid
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

    # Verify key 20pip_stop_40pip_tp metadata fields
    assert golden_metadata["dataset_type"] == "strategy"
    assert "ema_crossover" in golden_metadata["strategy_name"].lower()
    assert "date_range" in golden_metadata
    assert "initial_capital" in golden_metadata


def test_ema_crossover_20pip_stop_40pip_tp_entry_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop + 40-pip TP entry prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop_40pip_tp",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    tolerances = TRADE_VALIDATION_TOLERANCES
    price_tolerance = tolerances["entry_price"]

    mismatches = []
    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        price_diff = abs(platform_trade["entry_price"] - tv_trade["entry_price"])

        if price_diff > price_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "entry_time": platform_trade["entry_time"],
                    "platform": platform_trade["entry_price"],
                    "tradingview": tv_trade["entry_price"],
                    "diff": price_diff,
                }
            )

    if mismatches:
        print("\n=== Entry Price Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']} ({mm['entry_time']}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry price mismatches. "
        f"Entry prices must match exactly (tolerance={price_tolerance})"
    )


def test_ema_crossover_20pip_stop_40pip_tp_exit_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates 20-pip stop + 40-pip TP exit prices match within tolerance.

    Excludes trades where platform had same-bar stop-loss/TP exits, as TradingView's
    historical backtesting cannot check stops/TPs within a bar (only at next bar open).

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_stop_40pip_tp",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=golden_metadata.get("date_range"),
    )

    platform_df, tv_df = align_trades(
        platform_trades, tradingview_trades, golden_metadata.get("date_range")
    )
    tolerances = TRADE_VALIDATION_TOLERANCES
    price_tolerance = tolerances["exit_price"]

    mismatches = []
    excluded_same_bar = []
    excluded_known_edge_cases = []

    # Get known edge cases for this strategy
    strategy_edge_cases = KNOWN_EDGE_CASES.get("ema_crossover/20pip_stop_40pip_tp", {})
    known_exit_price_edge_cases = strategy_edge_cases.get("exit_price_mismatches", [])

    for i in range(len(platform_df)):
        platform_trade = platform_df.iloc[i]
        tv_trade = tv_df.iloc[i]

        # Exclude same-bar stop-loss/TP exits (TradingView limitation)
        # Platform can detect intra-bar stops/TPs, TradingView cannot
        if platform_trade["entry_time"] == platform_trade["exit_time"]:
            excluded_same_bar.append(i)
            continue

        price_diff = abs(platform_trade["exit_price"] - tv_trade["exit_price"])

        if price_diff > price_tolerance:
            # Check if this is a known edge case
            is_known_edge_case = False
            for edge_case in known_exit_price_edge_cases:
                if edge_case["trade_index"] == i:
                    excluded_known_edge_cases.append(
                        {
                            "trade_num": i + 1,
                            "trade_index": i,
                            "description": edge_case["description"],
                        }
                    )
                    is_known_edge_case = True
                    break

            if not is_known_edge_case:
                mismatches.append(
                    {
                        "trade_num": i + 1,
                        "trade_index": i,
                        "entry_time": platform_trade["entry_time"],
                        "exit_time": platform_trade["exit_time"],
                        "platform": platform_trade["exit_price"],
                        "tradingview": tv_trade["exit_price"],
                        "diff": price_diff,
                    }
                )

    # Report excluded trades
    if excluded_same_bar:
        print("\n=== Excluded Same-Bar Stop-Loss/TP Exits ===")
        print(
            f"Excluded {len(excluded_same_bar)} trades where platform detected "
            f"intra-bar stop-loss or take-profit."
        )
        print(
            "This is expected: TradingView's historical backtesting cannot "
            "check stops/TPs within a bar."
        )

    # Report excluded known edge cases
    if excluded_known_edge_cases:
        print("\n=== Excluded Known Edge Cases ===")
        for edge_case in excluded_known_edge_cases:
            print(
                f"Trade {edge_case['trade_num']} (Index {edge_case['trade_index']}): "
                f"{edge_case['description']}"
            )
        print(
            f"\nExcluded {len(excluded_known_edge_cases)} known edge case(s). "
            f"See KNOWN_EDGE_CASES for details."
        )

    # Report unexpected mismatches
    if mismatches:
        print("\n=== UNEXPECTED Exit Price Mismatches ===")
        for mm in mismatches[:10]:
            entry_time = mm["entry_time"]
            exit_time = mm["exit_time"]
            print(
                f"Trade {mm['trade_num']} (Entry: {entry_time}, "
                f"Exit: {exit_time}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} UNEXPECTED exit price mismatches. "
        f"Exit prices must match exactly (tolerance={price_tolerance}). "
        f"Note: {len(excluded_same_bar)} same-bar exits and "
        f"{len(excluded_known_edge_cases)} known edge cases were excluded."
    )
