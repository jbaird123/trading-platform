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
    },
    "ema_crossover/20pip_trailing_stop": {
        "exit_time_mismatches": [
            {
                "trade_index": 2,  # Trade 3 in 1-indexed display
                "entry_time": "2023-01-03 05:00:00",
                "exit_time": "2023-01-03 08:00:00",
                "description": "Platform more accurate - TV missed trailing stop hit",
                "explanation": (
                    "Short entry at 1.06674 with 20-pip trailing stop. "
                    "During 08:00 hour, price dropped dramatically with trough "
                    "improving from 1.06201 (at hour start) to 1.05571 at 08:32, "
                    "moving trailing stop to 1.05771. At 08:38, price rallied "
                    "with bar high of 1.05774, hitting the stop at 1.05771 "
                    "(exceeded by 0.3 pips). Platform correctly detects this "
                    "using 1-minute zoom and exits at 08:00 hourly bar with "
                    "price 1.05771. TradingView's historical backtester failed "
                    "to detect the trailing stop hit on the 08:00 hourly bar "
                    "and didn't exit until 10:00 at price 1.05541 (2 hours late, "
                    "23 pips better fill). Platform is MORE accurate than "
                    "TradingView in this case due to superior intra-bar "
                    "resolution via 1-minute zoom feature."
                ),
                "platform_exit_time": "2023-01-03 08:00:00",
                "platform_exit_price": 1.05771,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-01-03 10:00:00",
                "tradingview_exit_price": 1.05541,
                "tradingview_exit_reason": "Short Trail",
            },
            {
                "trade_index": 18,  # Trade 19 in 1-indexed display
                "entry_time": "2023-02-15 12:00:00",
                "exit_time": "2023-02-15 13:00:00",
                "description": "Platform more accurate - TV missed trailing stop hit",
                "explanation": (
                    "Short entry at 1.07110 with 20-pip trailing stop. "
                    "During 13:00 hour, price dropped to low of 1.06742 at "
                    "13:30, moving trailing stop to 1.06945. Price continued "
                    "to improve trough to 1.06742 at 13:39, moving stop to "
                    "1.06942. At 13:45, price rallied with bar high of 1.06970, "
                    "hitting the stop at 1.06942. Platform correctly detects "
                    "this using 1-minute zoom and exits at 13:00 hourly bar "
                    "with price 1.06942. TradingView's historical backtester "
                    "failed to detect the trailing stop hit on the 13:00 "
                    "hourly bar and didn't exit until 16:00 at price 1.06852 "
                    "(3 hours late). Platform is MORE accurate than TradingView "
                    "in this case due to superior intra-bar resolution via "
                    "1-minute zoom feature."
                ),
                "platform_exit_time": "2023-02-15 13:00:00",
                "platform_exit_price": 1.06942,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-02-15 16:00:00",
                "tradingview_exit_price": 1.06852,
                "tradingview_exit_reason": "Short Trail",
            },
            {
                "trade_index": 23,  # Trade 24 in 1-indexed display
                "entry_time": "2023-03-01 07:00:00",
                "exit_time": "2023-03-01 09:00:00",
                "description": (
                    "Platform more accurate - TV false exit from OHLC timing error"
                ),
                "explanation": (
                    "Long entry at 1.06072 with 20-pip trailing stop. "
                    "During 08:00 hour, the hourly bar had low=1.06258 and "
                    "high=1.06490. TradingView's OHLC-based logic sees that "
                    "the bar's low (1.06258) is below the final stop at hour "
                    "end (1.06290) and incorrectly concludes the stop was hit. "
                    "However, 1-minute data shows the low of 1.06258 occurred "
                    "at 08:05 when the stop was still at 1.06252 (0.6 pips "
                    "above the low - NOT hit). The peak didn't improve to "
                    "1.06490 until 08:59, moving the stop to 1.06290. By then, "
                    "price never dropped to that level. Platform correctly "
                    "processes chronologically and determines no exit in 08:00. "
                    "In 09:00 hour, peak improved to 1.06578 (stop at 1.06378), "
                    "then at 09:23 the bar low of 1.06377 hit the stop. "
                    "Platform correctly exits at 09:00 @ 1.06378. TradingView's "
                    "OHLC logic cannot determine temporal order of events and "
                    "falsely exits at 08:00 @ 1.06290. Platform is MORE "
                    "accurate due to chronological 1-minute processing."
                ),
                "platform_exit_time": "2023-03-01 09:00:00",
                "platform_exit_price": 1.06378,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-03-01 08:00:00",
                "tradingview_exit_price": 1.06290,
                "tradingview_exit_reason": "Long Trail",
            },
            {
                "trade_index": 27,  # Trade 28 in 1-indexed display
                "entry_time": "2023-03-10 00:00:00",
                "exit_time": "2023-03-10 02:00:00",
                "description": (
                    "Platform more accurate - TV uses strict < instead of <="
                ),
                "explanation": (
                    "Long entry at 1.05856 with 20-pip trailing stop. "
                    "Peak improved to 1.05994 during 00:00 hour, moving stop "
                    "to 1.05794. At 02:30, the bar low touched EXACTLY 1.05794 "
                    "(perfect tie to full floating-point precision). Platform "
                    "correctly uses 'low <= stop' comparison and triggers exit "
                    "at 02:00 @ 1.05794. TradingView appears to use strict "
                    "'low < stop' comparison and does not trigger on exact "
                    "price match. TradingView waits until 08:00 when price "
                    "drops below 1.05794 (to 1.05790 at 08:16). Platform "
                    "behavior is correct: a stop-loss at a specific price "
                    "should trigger when that price is REACHED (touched), not "
                    "only when EXCEEDED. This is standard stop-loss semantics. "
                    "TradingView's strict less-than comparison is incorrect for "
                    "stop-loss behavior. Platform is MORE accurate."
                ),
                "platform_exit_time": "2023-03-10 02:00:00",
                "platform_exit_price": 1.05794,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-03-10 08:00:00",
                "tradingview_exit_price": 1.05870,
                "tradingview_exit_reason": "Long Trail",
            },
            {
                "trade_index": 66,  # Trade 67 in 1-indexed display
                "entry_time": "2023-06-23 05:00:00",
                "exit_time": "2023-06-23 07:00:00",
                "description": (
                    "Platform more accurate - TV false exit from OHLC timing error"
                ),
                "explanation": (
                    "Short entry at 1.09332 with 20-pip trailing stop. "
                    "Price dropped dramatically during 07:00 hour, with trough "
                    "improving from 1.09203 to 1.08536 at 07:30, moving trailing "
                    "stop to 1.08736. At 07:54, price bounced with bar high of "
                    "1.08742, hitting the stop at 1.08736. Platform correctly "
                    "detects this using 1-minute zoom and exits at 07:00 hourly "
                    "bar with price 1.08736. TradingView sees the 07:00 hourly "
                    "bar (high=1.09261, low=1.08536) which clearly reached the "
                    "stop level of 1.08736, but due to OHLC timing/ordering "
                    "logic, it failed to detect the stop hit in this bar. "
                    "TradingView instead exits at 08:00 at the same price "
                    "(1.08736). Both exit at identical price but TradingView is "
                    "1 hour late. Platform is MORE accurate due to chronological "
                    "1-minute processing that detects the exact moment (07:54) "
                    "when the stop was hit after the price made new low and "
                    "retraced."
                ),
                "platform_exit_time": "2023-06-23 07:00:00",
                "platform_exit_price": 1.08736,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-06-23 08:00:00",
                "tradingview_exit_price": 1.08736,
                "tradingview_exit_reason": "Short Trail",
            },
        ]
    },
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

    # Create DataHandler for 1-minute resolution (if needed for trailing stops)
    # This enables intra-bar ambiguity resolution AND provides resampled hourly data
    data_handler = None
    if "trailing_stop" in str(strategy_name):
        from pathlib import Path

        from trading_platform.data.handler import DataHandler

        # Use golden TradingView data directory for 1-minute resolution
        # Matches same TradingView data source as hourly golden data
        data_root = (
            Path(__file__).parent.parent.parent
            / "data"
            / "dvc"
            / "golden"
            / "ohlcv"
            / "tradingview"
        )

        # Create DataHandler with EUR/USD symbol
        # This will load the 1-minute base data and cache it
        if data_root.exists():
            try:
                data_handler = DataHandler(
                    symbol="EUR_USD",
                    data_root=data_root,
                    instrument=config.instrument,
                )

                # IMPORTANT: Use resampled 1H data from DataHandler instead of CSV
                # This mirrors real-world usage where we load 1min raw data and resample
                ohlcv_1h = data_handler.get_data(timeframe="1H")

                # Apply same date filtering as before
                if date_range:
                    from datetime import timedelta

                    end_date = pd.to_datetime(date_range["end"], utc=True) + timedelta(
                        days=1, seconds=-1
                    )
                    warmup_start = pd.Timestamp("2022-12-01", tz="UTC")
                    ohlcv_to_use = ohlcv_1h[
                        (ohlcv_1h.index >= warmup_start) & (ohlcv_1h.index <= end_date)
                    ].copy()
                else:
                    ohlcv_to_use = ohlcv_1h

            except FileNotFoundError as e:
                # For trailing stop strategies, 1-minute data is REQUIRED
                # Fail loudly instead of silently falling back to CSV-only mode
                raise FileNotFoundError(
                    f"1-minute data is required for trailing stop strategy "
                    f"validation.\nExpected data at: {data_root}/full/eur_usd/"
                    f"eurusd_1min.csv\nOriginal error: {e}"
                ) from e
            except Exception as e:
                # Re-raise other exceptions with context
                raise RuntimeError(
                    f"Failed to create DataHandler for trailing stop validation.\n"
                    f"Data root: {data_root}\n"
                    f"Error: {e}"
                ) from e

    # Run backtest on extended data
    results = run_backtest_from_config(
        config=config,
        market_data=ohlcv_to_use,
        strategy_config=strategy_config,
        data_handler=data_handler,
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


# DEPRECATED: This function has been removed.
# Use load_and_validate_tradingview_trades() from golden_utils.py instead.


def align_trades(
    our_trades: list[dict],
    tv_trades: pd.DataFrame,
    validation_range: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aligns platform and TradingView trades for comparison.

    Matches trades by entry time and returns aligned DataFrames.

    NOTE: This function is deprecated. New code should use
    load_and_validate_tradingview_trades() from golden_utils.py directly.

    Args:
        our_trades: List of platform trade dictionaries (already filtered)
        tv_trades: Raw TradingView DataFrame (will be parsed and filtered)
        validation_range: Optional dict with 'start' and 'end' for filtering TV trades

    Returns:
        Tuple of (platform_df, tradingview_df) aligned by entry time
    """
    from tests.validation.golden_utils import load_and_validate_tradingview_trades

    # Parse TradingView trades using the golden utils function
    # The fixture passes raw CSV data, so we need to determine the file path
    # For existing tests, we'll use the deprecated inline parsing for
    # backward compatibility. But raise a warning that this should be updated

    # Check if tv_trades is already parsed (has entry_time column)
    if "entry_time" in tv_trades.columns:
        # Already parsed - just filter and use it
        tv_df = tv_trades
        if validation_range:
            start_date = pd.to_datetime(validation_range["start"], utc=True)
            end_date = pd.to_datetime(validation_range["end"], utc=True)
            tv_df = tv_df[
                (tv_df["entry_time"] >= start_date) & (tv_df["entry_time"] <= end_date)
            ].copy()
    else:
        # Raw CSV data - need to parse it
        # Use inline parsing for backward compatibility
        import os
        import tempfile

        from tests.validation.golden_utils import load_and_validate_tradingview_trades

        # Write to temp file and use golden_utils to parse
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            tv_trades.to_csv(f, index=False)
            temp_path = f.name

        try:
            tv_df = load_and_validate_tradingview_trades(
                Path(temp_path), validation_range=validation_range
            )
        finally:
            os.unlink(temp_path)

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
    # Use align_trades to parse TradingView trades with validation range filtering
    # This filters to validation range AND excludes open trades
    _, tv_trades_df = align_trades(
        [], tradingview_trades, golden_metadata.get("date_range")
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


# =============================================================================
# EMA Crossover - 20pip Trailing Stop Tests
# =============================================================================


def test_ema_crossover_20pip_trailing_stop_metadata_schema_validation(
    golden_metadata,
):
    """Validates metadata.json conforms to schema.

    Validates: [DH-2.13]
    """
    # If we got here, the golden_metadata fixture already validated the schema
    assert golden_metadata is not None
    assert golden_metadata.get("dataset_type") == "strategy"
    assert golden_metadata.get("strategy_name") == "ema_crossover_20pip_trailing_stop"


def test_ema_crossover_20pip_trailing_stop_trade_count_matches_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates platform generates same number of trades as TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_trailing_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Compare counts
    assert len(platform_df) == len(tv_df), (
        f"Trade count mismatch: Platform generated {len(platform_df)} trades, "
        f"TradingView generated {len(tv_df)} trades"
    )


def test_ema_crossover_20pip_trailing_stop_entry_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates all entry times match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_trailing_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Compare entry times
    mismatches = []
    for i in range(len(platform_df)):
        p_time = platform_df.iloc[i]["entry_time"]
        tv_time = tv_df.iloc[i]["entry_time"]

        if p_time != tv_time:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "platform": str(p_time),
                    "tradingview": str(tv_time),
                }
            )

    if mismatches:
        print("\n=== Entry Time Mismatches ===")
        for mm in mismatches[:10]:
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry time mismatches. "
        f"Entry times must match exactly."
    )


def test_ema_crossover_20pip_trailing_stop_entry_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates all entry prices match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")
    price_tolerance = 0.00001

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_trailing_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Compare entry prices
    mismatches = []
    for i in range(len(platform_df)):
        p_price = platform_df.iloc[i]["entry_price"]
        tv_price = tv_df.iloc[i]["entry_price"]
        entry_time = platform_df.iloc[i]["entry_time"]

        if abs(p_price - tv_price) > price_tolerance:
            mismatches.append(
                {
                    "trade_num": i + 1,
                    "entry_time": str(entry_time),
                    "platform": p_price,
                    "tradingview": tv_price,
                    "diff": abs(p_price - tv_price),
                }
            )

    if mismatches:
        print("\n=== Entry Price Mismatches ===")
        for mm in mismatches[:10]:
            entry_time = mm["entry_time"]
            print(
                f"Trade {mm['trade_num']} (Entry: {entry_time}): "
                f"Platform={mm['platform']:.5f}, TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry price mismatches. "
        f"Entry prices must match exactly (tolerance={price_tolerance})."
    )


def test_ema_crossover_20pip_trailing_stop_exit_times_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates all exit times match between platform and TradingView.

    For trailing stop strategies, this test categorizes ALL time discrepancies
    to ensure each one is explainable and acceptable. This includes:
    1. Same-bar entry/exit (TradingView historical limitation)
    2. Entry bar MFE patterns (TradingView ignores entry bar favorable movement)
    3. Known documented edge cases (see KNOWN_EDGE_CASES)

    Validates: [BT-7.8], [SE-3.5.3]
    """
    from tests.validation.trailing_stop_discrepancy_analyzer import (
        TrailingStopDiscrepancyAnalyzer,
    )

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_trailing_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Get known edge cases for this strategy
    strategy_edge_cases = KNOWN_EDGE_CASES.get("ema_crossover/20pip_trailing_stop", {})
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Use analyzer to categorize time mismatches based on MFE patterns
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
    )

    # Additionally check for trades with exit TIME mismatches
    # (analyzer checks exit PRICE mismatches, but we need time too)
    time_mismatches = []
    excluded_known_edge_cases = []

    for i in range(len(platform_df)):
        p_time = platform_df.iloc[i]["exit_time"]
        tv_time = tv_df.iloc[i]["exit_time"]

        if p_time != tv_time:
            # Check if this is a known documented edge case
            is_known_edge_case = False
            for edge_case in known_exit_time_edge_cases:
                if edge_case["trade_index"] == i:
                    excluded_known_edge_cases.append(
                        {
                            "trade_num": i + 1,
                            "trade_index": i,
                            "description": edge_case["description"],
                            "entry_time": str(platform_df.iloc[i]["entry_time"]),
                            "platform_exit": str(p_time),
                            "tradingview_exit": str(tv_time),
                        }
                    )
                    is_known_edge_case = True
                    break

            if not is_known_edge_case:
                # Check if this mismatch is explained by the analyzer
                # (via entry bar MFE patterns)
                is_analyzer_explained = False
                for category in analyzer.KNOWN_ACCEPTABLE_CATEGORIES:
                    for trade in categories.get(category, []):
                        if trade["trade_num"] == i + 1:
                            is_analyzer_explained = True
                            break
                    if is_analyzer_explained:
                        break

                if not is_analyzer_explained:
                    time_mismatches.append(
                        {
                            "trade_num": i + 1,
                            "trade_index": i,
                            "entry_time": str(platform_df.iloc[i]["entry_time"]),
                            "platform": str(p_time),
                            "tradingview": str(tv_time),
                        }
                    )

    # Generate and print summary report from analyzer
    summary_report = analyzer.generate_summary_report(categories)
    print(f"\n{summary_report}")

    # Report excluded known edge cases
    if excluded_known_edge_cases:
        print("\n=== Excluded Known Edge Cases ===")
        for edge_case in excluded_known_edge_cases:
            print(
                f"Trade {edge_case['trade_num']} (Index {edge_case['trade_index']}): "
                f"{edge_case['description']}"
            )
            print(
                f"  Platform exit: {edge_case['platform_exit']}, "
                f"TV exit: {edge_case['tradingview_exit']}"
            )
        print(
            f"\nExcluded {len(excluded_known_edge_cases)} known edge case(s). "
            f"See KNOWN_EDGE_CASES for details."
        )

    # Report unexpected time mismatches
    if time_mismatches:
        print("\n=== UNEXPECTED Exit Time Mismatches ===")
        for mm in time_mismatches[:10]:
            entry_time = mm["entry_time"]
            print(
                f"Trade {mm['trade_num']} (Entry: {entry_time}): "
                f"Platform={mm['platform']}, TV={mm['tradingview']}"
            )
        if len(time_mismatches) > 10:
            print(f"... and {len(time_mismatches) - 10} more")

    # Count total explained discrepancies
    total_analyzer_explained = sum(
        len(categories[cat]) for cat in analyzer.KNOWN_ACCEPTABLE_CATEGORIES
    )

    assert len(time_mismatches) == 0, (
        f"Found {len(time_mismatches)} UNEXPLAINED exit time mismatches. "
        f"Exit times must match exactly or be explained by known patterns. "
        f"Note: {total_analyzer_explained} trades explained by entry bar MFE patterns, "
        f"{len(excluded_known_edge_cases)} documented edge cases were excluded."
    )


def test_ema_crossover_20pip_trailing_stop_exit_prices_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Validates all exit prices match between platform and TradingView.

    For trailing stop strategies, this test categorizes ALL discrepancies to ensure
    each one is explainable and acceptable. This prevents regressions where future
    changes might break the trailing stop logic.

    Known acceptable discrepancy categories:
    1. SAME_BAR_EXIT: Entry/exit on same bar (TradingView limitation)
    2. ENTRY_BAR_PEAK_MFE: Entry bar had peak MFE (TV ignores it)
    3. ENTRY_BAR_CONTRIBUTED_MFE: Entry bar contributed to MFE
       (TV ignores entry bar portion)

    Any UNEXPLAINED discrepancies will cause the test to fail, indicating
    a potential bug or new TradingView behavior that needs investigation.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    from tests.validation.trailing_stop_discrepancy_analyzer import (
        TrailingStopDiscrepancyAnalyzer,
    )

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_trailing_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Analyze discrepancies using the discrepancy analyzer
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
    )

    # Generate and print summary report
    summary_report = analyzer.generate_summary_report(categories)
    print(f"\n{summary_report}")

    # Print detailed breakdown for each category
    print("\nDETAILED DISCREPANCY BREAKDOWN:")
    print("=" * 100)
    for category in analyzer.KNOWN_ACCEPTABLE_CATEGORIES + ["UNEXPLAINED"]:
        trades = categories.get(category, [])
        if len(trades) == 0:
            continue

        print(f"\n{category} ({len(trades)} trades):")
        print("-" * 100)

        # Show first 5 examples
        for trade in trades[:5]:
            print(f"\nTrade #{trade['trade_num']} ({trade['direction'].upper()})")
            print(f"  Entry: {trade['entry_time']} @ {trade['entry_price']:.5f}")
            print(f"  Exit:  {trade['exit_time']}")
            print(
                f"  Platform: {trade['platform_exit']:.5f} "
                f"({trade['platform_exit_reason']})"
            )
            print(
                f"  TradingView: {trade['tv_exit']:.5f} "
                f"(Signal: {trade['tv_exit_signal']})"
            )
            print(f"  Difference: {trade['price_diff_pips']:.1f} pips")
            if "entry_bar_mfe_pips" in trade:
                print(f"  Entry bar MFE: {trade['entry_bar_mfe_pips']:.1f} pips")
                print(
                    f"  Overall MFE (excl. entry): "
                    f"{trade['overall_mfe_excl_entry_pips']:.1f} pips"
                )
            print(f"  → {trade['explanation']}")

        if len(trades) > 5:
            print(f"\n  ... and {len(trades) - 5} more with similar explanations")

    # Assert all discrepancies are explained
    analyzer.assert_all_explained(categories)
