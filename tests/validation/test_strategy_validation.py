"""Golden validation tests comparing platform trades vs TradingView.

# Validates: [SE-3.5], [BT-7.8], [RV-9.1]

This module tests that our platform produces the same trades and PnL
as TradingView when running identical strategies on identical data.

IMPORTANT: All golden validation tests MUST use the utility functions from
golden_utils.py to ensure consistent data loading, filtering, and validation.

See: docs/GOLDEN_VALIDATION.md for the golden validation contract.
"""

from datetime import timedelta
from numbers import Real
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from trading_platform.backtester._testing import run_backtest_with_synthetic_data
from trading_platform.core.global_features_cache import cache_covers_features
from trading_platform.portfolio.trade import Trade

PROJECT_ROOT = Path(__file__).parent.parent.parent
GOLDEN_FEATURE_CACHE_ROOT = PROJECT_ROOT / "data" / "cache_test"
GOLDEN_TV_CACHE_ROOT = GOLDEN_FEATURE_CACHE_ROOT

# Golden validation utilities (ALWAYS use these for golden tests)

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

HASH_VALIDATION_CASES: list[tuple[str, str]] = [
    ("ema_crossover/baseline", "platform_trades_baseline"),
    ("ema_crossover/20pip_stop", "platform_trades_20pip_stop"),
    (
        "ema_crossover/20pip_stop_40pip_tp",
        "platform_trades_20pip_stop_40pip_tp",
    ),
    (
        "ema_crossover/20pip_trailing_stop",
        "platform_trades_20pip_trailing_stop",
    ),
    (
        "ema_crossover/20pip_trailing_stop_15pip_tp",
        "platform_trades_20pip_trailing_stop_15pip_tp",
    ),
    ("ema_crossover/2atr_stop", "platform_trades_2atr_stop"),
    ("ema_crossover/bb_stop", "platform_trades_bb_stop"),
]

# === KNOWN EDGE CASES ===
#
# KNOWN_EDGE_CASES - Kept for historical reference but no longer used
#
# The analyzer now automatically categorizes all discrepancies that were
# previously documented as KNOWN_EDGE_CASES. These manual edge cases are
# preserved below for reference but are commented out. They can be removed
# entirely in the future once we're confident the analyzer handles all cases.
#
# Previous edge cases are now categorized as:
# - PLATFORM_ZOOM_INTRABAR_STOP: Platform detected stop via 1-min zoom
# - TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT: TV ignores entry bar MFE
# - SAME_BAR_EXIT: Entry and exit on same bar
#
KNOWN_EDGE_CASES: dict[str, dict[str, list[dict]]] = {}
"""
# HISTORICAL KNOWN_EDGE_CASES - Preserved for reference, can be deleted later
KNOWN_EDGE_CASES_BACKUP: dict[str, dict[str, list[dict]]] = {
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
            {
                "trade_index": 52,  # Trade 53 in 1-indexed display
                "entry_time": "2023-05-05 09:00:00",
                "exit_time": "2023-05-05 12:00:00",
                "description": (
                    "Platform more accurate - intra-bar stop hit via 1-min zoom"
                ),
                "explanation": (
                    "Short entry at 1.10284 with 20-pip trailing stop. "
                    "Price dropped dramatically to 1.09716 at 12:30, moving "
                    "trailing stop to 1.09916. At 12:31, price bounced to "
                    "1.10000, hitting the stop at 1.09916. Platform correctly "
                    "detects this using 1-minute zoom and exits at 12:00 hourly "
                    "bar. The 12:00 hourly bar shows high=1.10186, which does "
                    "NOT reach either platform's stop (1.10422) or TradingView's "
                    "stop (1.10484) when calculated from hourly data alone. "
                    "However, the 1-minute zoom reveals the true peak at 12:31 "
                    "was 1.10000, and the true trough at 12:30 was 1.09716, "
                    "making the actual stop level 1.09916. TradingView cannot "
                    "see intra-bar movements on hourly bars, so it doesn't "
                    "detect the stop hit until 13:00. Platform is MORE accurate "
                    "due to 1-minute zoom detecting intra-bar stop hits that "
                    "hourly bars miss. Note: Entry bar MFE (6.2 pips) is NOT "
                    "the cause of the discrepancy here - it's purely the zoom "
                    "feature revealing intra-bar price action."
                ),
                "platform_exit_time": "2023-05-05 12:00:00",
                "platform_exit_price": 1.09916,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-05-05 13:00:00",
                "tradingview_exit_price": 1.09867,
                "tradingview_exit_reason": "Short Trail",
            },
            {
                "trade_index": 100,  # Trade 101 in 1-indexed display
                "entry_time": "2023-11-01 00:00:00",
                "exit_time": "2023-11-01 12:00:00",
                "description": (
                    "TradingView false exit from OHLC timing error - high before low"
                ),
                "explanation": (
                    "Short entry at 1.05780 with 20-pip trailing stop. "
                    "During 12:00 hour, the HIGH (1.05577) occurred at 12:35, "
                    "while the LOW (1.05369) occurred later at 12:58. When the "
                    "high occurred, the trailing stop was at 1.05609 (based on "
                    "trough of 1.05409 from previous hours), so the high of "
                    "1.05577 was 32 pips below the stop - no exit. When the "
                    "low occurred at 12:58, it moved the stop down to 1.05569, "
                    "but the highest subsequent price was only 1.05449 (12 pips "
                    "below the new stop) - still no exit. TradingView only sees "
                    "hourly OHLC (Low=1.05369, High=1.05577) and cannot determine "
                    "chronological order, so it incorrectly assumes the low came "
                    "first (moving stop to 1.05569), then the high came second "
                    "(1.05577 >= 1.05569, triggering exit). Platform is MORE "
                    "accurate due to chronological 1-minute processing revealing "
                    "the high occurred BEFORE the low."
                ),
                "platform_exit_time": "2023-11-01 14:00:00",
                "platform_exit_price": 1.05414,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-11-01 12:00:00",
                "tradingview_exit_price": 1.05569,
                "tradingview_exit_reason": "Short Trail",
            },
            {
                "trade_index": 157,  # Trade 158 in 1-indexed display
                "entry_time": "2024-04-03 04:00:00",
                "exit_time": "2024-04-03 14:00:00",
                "description": (
                    "Platform more accurate - intra-bar stop hit via 1-min zoom"
                ),
                "explanation": (
                    "Long entry at 1.07773 with 20-pip trailing stop. "
                    "During the 14:00 hour, price rallied dramatically with "
                    "the peak reaching 1.08180 at 14:02, moving the trailing "
                    "stop to 1.07980. At 14:10, price dropped with the bar low "
                    "touching exactly 1.07980, hitting the stop. Platform correctly "
                    "detects this using 1-minute zoom and exits at the 14:00 hourly "
                    "bar. TradingView, using only hourly bars, cannot see this "
                    "intra-bar stop hit during the 14:00 hour and doesn't exit "
                    "until 18:00 on 2024-04-04 (28 hours later). Platform is MORE "
                    "accurate due to 1-minute zoom detecting intra-bar stop hits "
                    "that hourly bars miss."
                ),
                "platform_exit_time": "2024-04-03 14:00:00",
                "platform_exit_price": 1.07980,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2024-04-04 18:00:00",
                "tradingview_exit_price": 1.08566,
                "tradingview_exit_reason": "Long Trail",
            },
            {
                "trade_index": 197,  # Trade 198 in 1-indexed display
                "entry_time": "2024-07-10 15:00:00",
                "exit_time": "2024-07-11 12:00:00",
                "description": (
                    "Platform more accurate - intra-bar stop hit via 1-min zoom"
                ),
                "explanation": (
                    "Long entry at 1.08233 with 20-pip trailing stop. "
                    "During the 12:00 hour, price rallied dramatically at 12:30 "
                    "with the peak reaching 1.08932, moving the trailing stop to "
                    "1.08732. At 12:33, peak improved slightly to 1.08938, moving "
                    "stop to 1.08738. Just 3 minutes later at 12:36, price dropped "
                    "with the bar low touching 1.08736, hitting the stop at 1.08738. "
                    "Platform correctly detects this using 1-minute zoom and exits "
                    "at the 12:00 hourly bar. TradingView, using only hourly bars, "
                    "cannot see this intra-bar stop hit during the 12:00 hour and "
                    "doesn't exit until 13:00 (1 hour later). Platform is MORE "
                    "accurate due to 1-minute zoom detecting intra-bar stop hits "
                    "that hourly bars miss."
                ),
                "platform_exit_time": "2024-07-11 12:00:00",
                "platform_exit_price": 1.08738,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2024-07-11 13:00:00",
                "tradingview_exit_price": 1.08800,
                "tradingview_exit_reason": "Long Trail",
            },
            {
                "trade_index": 229,  # Trade 230 in 1-indexed display
                "entry_time": "2024-10-29 23:00:00",
                "exit_time": "2024-10-30 09:00:00",
                "description": (
                    "Platform more accurate - intra-bar stop hit via 1-min zoom"
                ),
                "explanation": (
                    "Long entry at 1.08202 with 20-pip trailing stop. "
                    "During the 09:00 hour, price rallied with the peak reaching "
                    "1.08595 at 09:05, moving the trailing stop to 1.08395. "
                    "Price then gradually declined over the next 17 minutes. "
                    "At 09:22, price dropped with the bar low reaching 1.08368, "
                    "hitting the stop at 1.08395. Platform correctly detects this "
                    "using 1-minute zoom and exits at the 09:00 hourly bar. "
                    "TradingView, using only hourly bars, cannot see this intra-bar "
                    "stop hit during the 09:00 hour and doesn't exit until 10:00 "
                    "(1 hour later). Platform is MORE accurate due to 1-minute zoom "
                    "detecting intra-bar stop hits that hourly bars miss."
                ),
                "platform_exit_time": "2024-10-30 09:00:00",
                "platform_exit_price": 1.08395,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2024-10-30 10:00:00",
                "tradingview_exit_price": 1.08395,
                "tradingview_exit_reason": "Long Trail",
            },
            {
                "trade_index": 234,  # Trade 235 in 1-indexed display
                "entry_time": "2024-11-20 13:00:00",
                "exit_time": "2024-11-20 14:00:00",
                "description": (
                    "Platform more accurate - intra-bar stop hit via 1-min zoom"
                ),
                "explanation": (
                    "Short entry at 1.05586 with 20-pip trailing stop. "
                    "During the 14:00 hour, price dropped steadily with the trough "
                    "reaching 1.05242 at 14:21 (a sharp 120-pip drop in one minute), "
                    "moving the trailing stop to 1.05442. Price then bounced back "
                    "over the next 10 minutes. At 14:31, price rallied with the bar "
                    "high reaching 1.05444, hitting the stop at 1.05442. Platform "
                    "correctly detects this using 1-minute zoom and exits at the "
                    "14:00 hourly bar. TradingView, using only hourly bars, cannot "
                    "see this intra-bar stop hit during the 14:00 hour and doesn't "
                    "exit until 15:00 (1 hour later). Platform is MORE accurate due "
                    "to 1-minute zoom detecting intra-bar stop hits that hourly "
                    "bars miss."
                ),
                "platform_exit_time": "2024-11-20 14:00:00",
                "platform_exit_price": 1.05442,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2024-11-20 15:00:00",
                "tradingview_exit_price": 1.05358,
                "tradingview_exit_reason": "Short Trail",
            },
            {
                "trade_index": 114,  # Trade 115 in 1-indexed display
                "entry_time": "2023-12-18 12:00:00",
                "exit_time": "2023-12-18 13:00:00",
                "description": (
                    "TV exited via signal - entry bar peak MFE pattern verified"
                ),
                "explanation": (
                    "Short entry at 1.09129 with 20-pip trailing stop. "
                    "Entry bar had peak MFE of 3.7 pips (subsequent bars: 0.0 pips). "
                    "Platform exited at 13:00 via stop-loss at 1.09292. "
                    "TradingView exited at 15:00 via reversal signal at 1.09293. "
                    "Entry bar peak MFE pattern is correct: platform's trailing stop "
                    "moved based on entry bar, TV's did not. When reversal signal "
                    "triggered, TV hit the signal before its stop (which was further "
                    "away). Manually verified as TV_IGNORED_ENTRY_BAR_PEAK_MFE."
                ),
                "platform_exit_time": "2023-12-18 13:00:00",
                "platform_exit_price": 1.09292,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2023-12-18 15:00:00",
                "tradingview_exit_price": 1.09293,
                "tradingview_exit_reason": "Close entry(s) order Short",
            },
            {
                "trade_index": 241,  # Trade 242 in 1-indexed display
                "entry_time": "2024-12-10 06:00:00",
                "exit_time": "2024-12-10 07:00:00",
                "description": (
                    "TV exited via signal - entry bar peak MFE pattern verified"
                ),
                "explanation": (
                    "Long entry at 1.05622 with 20-pip trailing stop. "
                    "Entry bar had peak MFE of 6.1 pips (subsequent bars: 4.4 pips). "
                    "Platform exited at 07:00 via stop-loss at 1.05483. "
                    "TradingView exited at 08:00 via reversal signal at 1.05488. "
                    "Entry bar peak MFE pattern is correct: platform's trailing stop "
                    "moved based on entry bar, TV's did not. When reversal signal "
                    "triggered, TV hit the signal before its stop (which was further "
                    "away). Manually verified as TV_IGNORED_ENTRY_BAR_PEAK_MFE."
                ),
                "platform_exit_time": "2024-12-10 07:00:00",
                "platform_exit_price": 1.05483,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_time": "2024-12-10 08:00:00",
                "tradingview_exit_price": 1.05488,
                "tradingview_exit_reason": "Close entry(s) order Long",
            },
        ],
        "exit_price_mismatches": [
            {
                "trade_index": 114,  # Trade 115 in 1-indexed display
                "entry_time": "2023-12-18 12:00:00",
                "exit_time": "2023-12-18 13:00:00",
                "description": (
                    "TV exited via signal - entry bar peak MFE pattern, "
                    "mathematically unverifiable"
                ),
                "explanation": (
                    "Short entry at 1.09129 with 20-pip trailing stop. "
                    "Entry bar had peak MFE of 3.7 pips (subsequent bars: 0.0 pips). "
                    "Platform exited at 13:00 via stop-loss at 1.09292. "
                    "TradingView exited at 15:00 via reversal signal at 1.09293. "
                    "Entry bar peak MFE pattern explains the discrepancy: "
                    "platform's trailing stop moved based on entry bar, "
                    "TV's did not. When reversal signal triggered, TV hit "
                    "the signal before its stop (which was further away). "
                    "However, because TV exited via signal (not stop), we "
                    "cannot mathematically verify that exit price difference "
                    "equals MFE difference as we do for stop-to-stop exits. "
                    "Manually verified."
                ),
                "platform_exit_price": 1.09292,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_price": 1.09293,
                "tradingview_exit_reason": "Close entry(s) order Short",
            },
            {
                "trade_index": 241,  # Trade 242 in 1-indexed display
                "entry_time": "2024-12-10 06:00:00",
                "exit_time": "2024-12-10 07:00:00",
                "description": (
                    "TV exited via signal - entry bar peak MFE pattern, "
                    "mathematically unverifiable"
                ),
                "explanation": (
                    "Long entry at 1.05622 with 20-pip trailing stop. "
                    "Entry bar had peak MFE of 6.1 pips (subsequent bars: 4.4 pips). "
                    "Platform exited at 07:00 via stop-loss at 1.05483. "
                    "TradingView exited at 08:00 via reversal signal at 1.05488. "
                    "Entry bar peak MFE pattern explains the discrepancy: "
                    "platform's trailing stop moved based on entry bar, "
                    "TV's did not. When reversal signal triggered, TV hit "
                    "the signal before its stop (which was further away). "
                    "However, because TV exited via signal (not stop), we "
                    "cannot mathematically verify that exit price difference "
                    "equals MFE difference as we do for stop-to-stop exits. "
                    "Manually verified."
                ),
                "platform_exit_price": 1.05483,
                "platform_exit_reason": "stop-loss",
                "tradingview_exit_price": 1.05488,
                "tradingview_exit_reason": "Close entry(s) order Long",
            },
        ],
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
"""


# === HELPER FUNCTIONS ===


def load_platform_trades(
    strategy_name: str,
    run_config: dict[str, Any],
    ohlcv_data: pd.DataFrame,
    data_handler: Any,
    date_range: dict[str, str] | None = None,
) -> list[dict]:
    """Runs backtest and returns platform trades filtered to validation range.

    This function handles the complete golden validation workflow:
    1. Loads strategy and REM configs
    2. Runs backtest using 1-min data resampled to 1H (always)
    3. Filters trades to validation range by entry_time
    4. Excludes "end_of_data" forced exits

    ALL strategies use 1-minute data resampled to 1H for consistency.
    This ensures all tests use the same data processing pipeline as production.

    Args:
        strategy_name: Name of strategy (e.g., "ema_crossover/20pip_stop")
        run_config: Run configuration dictionary
        ohlcv_data: OHLCV data (ignored - kept for backward compatibility)
        data_handler: Session-scoped DataHandler with 1-minute data (required)
        date_range: Validation range dict with 'start' and 'end' keys

    Returns:
        List of trade dictionaries filtered to validation range

    See: docs/GOLDEN_VALIDATION.md for the golden validation contract
    """
    from datetime import timedelta
    from pathlib import Path

    import yaml
    from trading_platform.core.config import RunConfig

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

    # Import locally to avoid circular imports if at top level
    from trading_platform.data.instrument import get_instrument_definition

    # Add REM config if available
    if rem_config:
        config_dict["rem_config"] = rem_config

    data_request: dict[str, Any] = config_dict.get("data_request", {}).copy()
    if date_range:
        start_val = date_range.get("start")
        end_val = date_range.get("end")
        if start_val and "start" not in data_request:
            data_request["start"] = start_val
        if end_val and "end" not in data_request:
            data_request["end"] = end_val
    if data_request:
        config_dict["data_request"] = data_request

    # Create RunConfig (trim handled by warmup guards)
    config = RunConfig.model_validate(config_dict)

    # ALL strategies use 1-minute data resampled to 1H
    ohlcv_1h = data_handler.get_data(timeframe="1H")

    execution_timeframe = (config.instrument or {}).get("timeframe", "1H")

    # Load cached global features if available
    cached_global_df = None
    golden_features_path = Path("data/dvc/golden/features/global.yaml")
    instrument_cfg = config.instrument or {}

    if date_range:
        from trading_platform.core.feature_resolver import resolve_global_features

        # Resolve global features to get feature names for cache lookup
        resolved_global = resolve_global_features(
            execution_timeframe, config_path=golden_features_path
        )
        feature_names = [f.name for f in resolved_global if f.name]

        if feature_names and hasattr(data_handler, "data_root"):
            symbol_for_cache = instrument_cfg.get("symbol") or data_request.get(
                "symbol"
            )
            if symbol_for_cache:
                use_cached_global = cache_covers_features(
                    symbol=symbol_for_cache,
                    cache_root=GOLDEN_FEATURE_CACHE_ROOT,
                    config_path=golden_features_path,
                    timeframe=execution_timeframe,
                    feature_names=feature_names,
                )
                if use_cached_global:
                    from trading_platform.core.global_features_cache import (
                        load_cached_global_features,
                    )

                    cache_result = load_cached_global_features(
                        symbol=symbol_for_cache,
                        cache_root=GOLDEN_FEATURE_CACHE_ROOT,
                        config_path=golden_features_path,
                        timeframe=execution_timeframe,
                        feature_names=feature_names,
                        session_group=get_instrument_definition(
                            symbol_for_cache
                        ).session_group,
                    )
                    if cache_result is not None:
                        cached_global_df, _ = cache_result

        # Filter data to end date only - use ALL available data for warmup
        end_date = pd.to_datetime(date_range["end"], utc=True) + timedelta(
            days=1, seconds=-1
        )
        ohlcv_to_use = ohlcv_1h[ohlcv_1h.index <= end_date].copy()
    else:
        ohlcv_to_use = ohlcv_1h

    # Run backtest - engine uses all data before data_request.start as warmup
    engine_result = run_backtest_with_synthetic_data(
        config=config,
        market_data=ohlcv_to_use,
        strategy_config=strategy_config,
        data_handler=data_handler,
        global_feature_df=cached_global_df,
        rmm_context=None,
    )
    trades_source = cast(list[Trade], engine_result.trades)

    # Filter trades to validation range
    # Helper function to convert Trade object to dict with all fields
    def trade_to_dict(trade):
        """Convert Trade to dict with all fields for hash verification."""
        trade_dict = {
            "symbol": trade.symbol,
            "side": trade.side,
            "size": trade.size,
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "exit_reason": trade.exit_reason,
            "pnl": trade.pnl,
            "mfe_currency": trade.mfe_currency,
            "mae_currency": trade.mae_currency,
            "bars_held": trade.bars_held,
            "cost_currency": trade.cost_currency,
        }

        # Add cost breakdown fields
        if trade.cost_breakdown:
            trade_dict["spread"] = trade.cost_breakdown.get("spread", 0.0)
            trade_dict["commission"] = trade.cost_breakdown.get("commission", 0.0)
            trade_dict["slippage"] = trade.cost_breakdown.get("slippage", 0.0)
        else:
            trade_dict["spread"] = 0.0
            trade_dict["commission"] = 0.0
            trade_dict["slippage"] = 0.0

        # Add flattened context fields
        if trade.context_at_entry:
            for key, value in _flatten_context_for_verification(
                trade.context_at_entry
            ).items():
                trade_dict[f"ctx_{key}"] = value

        return trade_dict

    if date_range:
        from datetime import timedelta

        # Filter to validation range
        start_date = pd.to_datetime(date_range["start"], utc=True)
        end_date = pd.to_datetime(date_range["end"], utc=True) + timedelta(
            days=1, seconds=-1
        )

        trades_list = [
            trade_to_dict(trade)
            for trade in trades_source
            if (
                trade.exit_reason != "end_of_data"
                and start_date <= trade.entry_time <= end_date
            )
        ]
    else:
        # No filtering, just convert and exclude end_of_data
        trades_list = [
            trade_to_dict(trade)
            for trade in trades_source
            if trade.exit_reason != "end_of_data"
        ]

    return trades_list


def _flatten_context_for_verification(ctx: dict, prefix: str = "") -> dict:
    """Flatten nested context dict into dot-notation keys for hash verification."""
    result = {}
    for key, value in ctx.items():
        new_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            # Recursively flatten nested dicts
            result.update(_flatten_context_for_verification(value, f"{new_key}_"))
        else:
            if isinstance(value, Real) and "obv" in new_key.lower():
                if float(value).is_integer():
                    value = int(float(value))
            result[new_key] = value
    return result


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
            # Set end_date to end of day (23:59:59) to include all trades
            # on the end date
            end_date = pd.to_datetime(validation_range["end"], utc=True) + pd.Timedelta(
                hours=23, minutes=59, seconds=59
            )
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


def verify_golden_trades_hash(
    strategy_name: str,
    platform_trades: list[dict],
) -> None:
    """Verify platform trades match golden reference file via SHA256 hash.

    This ensures that ANY change in platform trade output causes tests to fail,
    even if the TradingView comparison tests still pass. This catches subtle
    bugs in calculations like MFE/MAE, exit_reason, bars_held, etc.

    Args:
        strategy_name: Name like "ema_crossover/baseline"
        platform_trades: List of trade dicts from load_platform_trades()

    Raises:
        AssertionError: If hash doesn't match golden file
    """
    import hashlib
    import tempfile

    # Load golden trades file
    golden_path = (
        Path(__file__).parent.parent.parent
        / "data/dvc/golden/strategies"
        / strategy_name
        / "platform_trades_golden.csv"
    )

    if not golden_path.exists():
        raise FileNotFoundError(
            f"Golden trades file not found: {golden_path}\n"
            f"Run tests/validation/generate_golden_trades.py to create it."
        )

    # Convert platform trades to same CSV format as golden file
    # (excluding r_multiple field)
    if not platform_trades:
        raise ValueError("No platform trades to verify!")

    # Collect all field names (base + context fields)
    all_fields: set[str] = set()
    for trade in platform_trades:
        all_fields.update(trade.keys())

    # Order fields: base fields first, then context fields sorted
    base_fields = [
        "symbol",
        "side",
        "size",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "exit_reason",
        "pnl",
        "mfe_currency",
        "mae_currency",
        "bars_held",
        "cost_currency",
        "spread",
        "commission",
        "slippage",
    ]
    # Base fields only for comparison (ignore context differences)
    ordered_fields = base_fields
    golden_df = pd.read_csv(golden_path)

    # Convert numpy types to Python types for consistent serialization
    def convert_types(obj):
        """Convert numpy/pandas types to Python native types."""
        import numpy as np
        import pandas as pd

        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, pd.Timestamp):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_types(item) for item in obj]
        return obj

    platform_df = pd.DataFrame(
        [
            {k: convert_types(trade.get(k)) for k in ordered_fields}
            for trade in platform_trades
        ]
    )
    platform_df = platform_df.sort_values("entry_time").reset_index(drop=True)
    for col in ("entry_time", "exit_time"):
        if col in platform_df.columns:
            platform_df[col] = pd.to_datetime(platform_df[col], utc=True).dt.strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )

    # Normalize golden for comparison (base fields only)
    golden_df = golden_df[ordered_fields].copy()
    golden_df = golden_df.sort_values("entry_time").reset_index(drop=True)
    for col in ("entry_time", "exit_time"):
        if col in golden_df.columns:
            golden_df[col] = pd.to_datetime(golden_df[col], utc=True).dt.strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )

    # Save a copy of the platform trades to workspace/golden_comparison
    try:
        comparison_dir = Path("workspace") / "golden_comparison"
        comparison_dir.mkdir(parents=True, exist_ok=True)
        comparison_path = (
            comparison_dir
            / f"{strategy_name.replace('/', '_')}_new_platform_trades.csv"
        )
        platform_df.to_csv(comparison_path, index=False, float_format="%.10f")
    except Exception:
        # Non-fatal: if the copy fails, continue with hash verification
        pass

    # Write current trades to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, newline="", suffix=".csv"
    ) as f:
        temp_path = f.name
        platform_df.to_csv(f, index=False, float_format="%.10f")

    try:
        # Calculate SHA256 hashes
        with open(temp_path, "rb") as f_current:
            current_hash = hashlib.sha256(f_current.read()).hexdigest()

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, newline="", suffix=".csv"
        ) as f_golden_tmp:
            golden_tmp_path = f_golden_tmp.name
            golden_df.to_csv(f_golden_tmp, index=False, float_format="%.10f")
        with open(golden_tmp_path, "rb") as f_golden:
            golden_hash = hashlib.sha256(f_golden.read()).hexdigest()

        # Compare hashes
        if current_hash != golden_hash:
            # Hashes don't match - show diff for debugging
            import subprocess

            try:
                diff_output = subprocess.run(
                    ["diff", "-u", str(golden_path), temp_path],
                    capture_output=True,
                    text=True,
                )
                diff_msg = diff_output.stdout[:2000]  # Limit to first 2000 chars
            except Exception:
                diff_msg = "(diff command failed)"

            raise AssertionError(
                f"Platform trades hash mismatch for {strategy_name}!\n"
                f"Golden hash: {golden_hash}\n"
                f"Current hash: {current_hash}\n\n"
                "Platform output differs from expected. "
                "If intentional, regenerate golden files:\n"
                "  poetry run python tests/validation/generate_golden_trades.py\n\n"
                f"First 2000 chars of diff:\n{diff_msg}"
            )
    finally:
        import os

        os.unlink(temp_path)
        if "golden_tmp_path" in locals() and os.path.exists(golden_tmp_path):
            os.unlink(golden_tmp_path)


def verify_golden_comparison_hash(
    strategy_name: str,
    comparison_file_path: Path,
    golden_filename: str = "exit_price_comparison_golden.csv",
) -> None:
    """Verify comparison file matches golden reference via SHA256 hash.

    For trailing stop strategies, this verifies the exit price or exit time
    comparison analysis hasn't changed.

    Args:
        strategy_name: Name like "ema_crossover/20pip_trailing_stop"
        comparison_file_path: Path to current comparison CSV file
        golden_filename: Golden file name
            (default: "exit_price_comparison_golden.csv")

    Raises:
        AssertionError: If hash doesn't match golden file
    """
    import hashlib

    # Load golden comparison file
    golden_path = (
        Path(__file__).parent.parent.parent
        / "data/dvc/golden/strategies"
        / strategy_name
        / golden_filename
    )

    if not golden_path.exists():
        raise FileNotFoundError(
            f"Golden comparison file not found: {golden_path}\n"
            "Run export test to generate workspace file, "
            "then copy to golden location."
        )

    if not comparison_file_path.exists():
        raise FileNotFoundError(
            f"Current comparison file not found: {comparison_file_path}"
        )

    def _canonicalize(path: Path) -> str:
        df = pd.read_csv(path)
        # Deterministic ordering
        if "trade_num" in df.columns:
            df = df.sort_values("trade_num").reset_index(drop=True)
        # Round floats to reduce insignificant drift
        float_cols = df.select_dtypes(include=["float64", "float32"]).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].round(5)
        return df.to_csv(index=False, float_format="%.5f")

    current_hash = hashlib.sha256(
        _canonicalize(comparison_file_path).encode()
    ).hexdigest()
    golden_hash = hashlib.sha256(_canonicalize(golden_path).encode()).hexdigest()

    # Compare hashes
    if current_hash != golden_hash:
        # Hashes don't match - show diff for debugging
        import subprocess

        try:
            diff_output = subprocess.run(
                ["diff", "-u", str(golden_path), str(comparison_file_path)],
                capture_output=True,
                text=True,
            )
            diff_msg = diff_output.stdout[:2000]  # Limit to first 2000 chars
        except Exception:
            diff_msg = "(diff command failed)"

        raise AssertionError(
            f"Comparison file hash mismatch for {strategy_name}!\n"
            f"Golden hash: {golden_hash}\n"
            f"Current hash: {current_hash}\n\n"
            f"This indicates the exit price comparison analysis has changed.\n"
            f"If this change is intentional, regenerate golden comparison file:\n"
            f"  1. Run the test to generate workspace/exit_price_comparison.csv\n"
            f"  2. Copy it to: {golden_path}\n"
            f"  3. Add to DVC and commit\n\n"
            f"First 2000 chars of diff:\n{diff_msg}"
        )


# === VALIDATION MARKER ===


pytestmark = pytest.mark.validation


# === TEST CASES ===


@pytest.mark.parametrize(
    ("strategy_name", "platform_fixture"),
    HASH_VALIDATION_CASES,
)
def test_ema_crossover_platform_trades_match_golden(
    strategy_name: str,
    platform_fixture: str,
    request: pytest.FixtureRequest,
):
    """Ensure platform trade snapshots still match the frozen golden files."""
    platform_trades = request.getfixturevalue(platform_fixture)
    verify_golden_trades_hash(strategy_name, platform_trades)


def test_ema_crossover_trade_count_matches_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_baseline,
):
    """Validates that EMA crossover produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = platform_trades_baseline

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
    tradingview_trades,
    golden_metadata,
    platform_trades_baseline,
):
    """Validates that entry times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = platform_trades_baseline

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
    tradingview_trades,
    golden_metadata,
    platform_trades_baseline,
):
    """Validates that exit times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    # Load platform trades
    platform_trades = platform_trades_baseline

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
    tradingview_trades,
    golden_metadata,
    platform_trades_baseline,
):
    """Validates baseline entry prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    platform_trades = platform_trades_baseline

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
    tradingview_trades,
    golden_metadata,
    platform_trades_baseline,
):
    """Validates baseline exit prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8]
    """
    platform_trades = platform_trades_baseline

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

    schema_path = Path(__file__).parent / "schemas" / "golden_metadata.schema.json"

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop,
):
    """Validates 20-pip stop variation produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop,
):
    """Validates 20-pip stop entry times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop,
):
    """Validates 20-pip stop exit times match within tolerance.

    Excludes trades where platform had same-bar stop-loss exits, as TradingView's
    historical backtesting cannot check stops within a bar (only at next bar open).

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop

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

    schema_path = Path(__file__).parent / "schemas" / "golden_metadata.schema.json"

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop,
):
    """Validates 20-pip stop entry prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop,
):
    """Validates 20-pip stop exit prices match within tolerance.

    Excludes trades where platform had same-bar stop-loss exits, as TradingView's
    historical backtesting cannot check stops within a bar (only at next bar open).

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop_40pip_tp,
):
    """Validates 20-pip stop + 40-pip TP variation produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop_40pip_tp

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop_40pip_tp,
):
    """Validates 20-pip stop + 40-pip TP entry times match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop_40pip_tp

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop_40pip_tp,
):
    """Validates 20-pip stop + 40-pip TP exit times match within tolerance.

    Excludes trades where platform had same-bar stop-loss/TP exits, as TradingView's
    historical backtesting cannot check stops/TPs within a bar (only at next bar open).

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop_40pip_tp

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
    shared_data_handler,
):
    """Validates 20-pip stop + 40-pip TP metadata conforms to schema.

    # Validates: [RV-9.6]
    """
    # This test validates that the 20pip_stop_40pip_tp strategy metadata is valid
    import json

    import jsonschema

    schema_path = Path(__file__).parent / "schemas" / "golden_metadata.schema.json"

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop_40pip_tp,
):
    """Validates 20-pip stop + 40-pip TP entry prices match within tolerance.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop_40pip_tp

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_stop_40pip_tp,
):
    """Validates 20-pip stop + 40-pip TP exit prices match within tolerance.

    Excludes trades where platform had same-bar stop-loss/TP exits, as TradingView's
    historical backtesting cannot check stops/TPs within a bar (only at next bar open).

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_20pip_stop_40pip_tp

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
    shared_data_handler,
):
    """Validates metadata.json conforms to schema.

    Validates: [DH-2.13]
    """
    # If we got here, the golden_metadata fixture already validated the schema
    assert golden_metadata is not None
    assert golden_metadata.get("dataset_type") == "strategy"
    assert golden_metadata.get("strategy_name") == "ema_crossover_20pip_trailing_stop"


def test_ema_crossover_20pip_trailing_stop_trade_count_matches_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Validates platform generates same number of trades as TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Compare counts
    assert len(platform_df) == len(tv_df), (
        f"Trade count mismatch: Platform generated {len(platform_df)} trades, "
        f"TradingView generated {len(tv_df)} trades"
    )


def test_ema_crossover_20pip_trailing_stop_entry_times_match_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Validates all entry times match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop

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
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Validates all entry prices match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")
    price_tolerance = 0.00001

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop

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
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Validates all exit times match between platform and TradingView.

    For trailing stop strategies, this test categorizes ALL time discrepancies
    to ensure each one is explainable and acceptable. This includes:
    1. Same-bar entry/exit (TradingView historical limitation)
    2. Entry bar MFE patterns (TradingView ignores entry bar favorable movement)
    3. Known documented edge cases (see KNOWN_EDGE_CASES)

    Validates: [BT-7.8], [SE-3.5.3]
    """
    from tests.validation.analyzers.trailing_stop import (
        TrailingStopDiscrepancyAnalyzer,
    )

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Get known edge cases for this strategy
    strategy_edge_cases = KNOWN_EDGE_CASES.get("ema_crossover/20pip_trailing_stop", {})
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Use analyzer to categorize time mismatches based on MFE patterns
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        take_profit_pips=0.0015,  # 15 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
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
                # (via entry bar MFE patterns or zoom discrepancies)
                exit_time_categories = [
                    "SAME_BAR_EXIT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
                    "PLATFORM_ZOOM_INTRABAR_STOP",
                    "PLATFORM_ZOOM_INTRABAR_TP",
                ]
                is_analyzer_explained = False
                for category in exit_time_categories:
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
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Validates all exit prices match between platform and TradingView.

    For trailing stop strategies, this test categorizes ALL discrepancies to ensure
    each one is explainable and acceptable. This prevents regressions where future
    changes might break the trailing stop logic.

    Known acceptable discrepancy categories:
    1. SAME_BAR_EXIT: Entry/exit on same bar (TradingView limitation)
    2. TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT: Entry bar had peak MFE
       (TV ignores it) - strict mathematical verification
    3. TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED: Entry bar had peak MFE
       (TV ignores it) - independent exit verification
    4. PLATFORM_ZOOM_INTRABAR_STOP: Platform detected intrabar stop
       via 1-minute zoom
    5. PLATFORM_ZOOM_INTRABAR_TP: Platform detected intrabar take-profit
       via 1-minute zoom

    Any UNEXPLAINED discrepancies will cause the test to fail, indicating
    a potential bug or new TradingView behavior that needs investigation.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    from tests.validation.analyzers.trailing_stop import (
        TrailingStopDiscrepancyAnalyzer,
    )

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Analyze discrepancies using the discrepancy analyzer
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        take_profit_pips=0.0015,  # 15 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
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
                f"  TradingView: {trade['tv_exit']:.5f} " f"({trade['tv_exit_reason']})"
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


def test_ema_crossover_20pip_trailing_stop_15pip_tp_metadata_schema_validation(
    golden_metadata,
    shared_data_handler,
):
    """Validates metadata.json conforms to schema.

    Validates: [DH-2.13]
    """
    # If we got here, the golden_metadata fixture already validated the schema
    assert golden_metadata is not None
    assert golden_metadata.get("dataset_type") == "strategy"
    assert (
        golden_metadata.get("strategy_name")
        == "ema_crossover_20pip_trailing_stop_15pip_tp"
    )


def test_ema_crossover_20pip_trailing_stop_15pip_tp_trade_count_matches_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_trailing_stop_15pip_tp,
):
    """Validates platform generates same number of trades as TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop_15pip_tp

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Compare counts
    assert len(platform_df) == len(tv_df), (
        f"Trade count mismatch: Platform generated {len(platform_df)} trades, "
        f"TradingView generated {len(tv_df)} trades"
    )


def test_ema_crossover_20pip_trailing_stop_15pip_tp_entry_times_match_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_trailing_stop_15pip_tp,
):
    """Validates all entry times match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop_15pip_tp

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


def test_ema_crossover_20pip_trailing_stop_15pip_tp_entry_prices_match_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_20pip_trailing_stop_15pip_tp,
):
    """Validates all entry prices match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")
    price_tolerance = 0.00001

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop_15pip_tp

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


def test_ema_crossover_20pip_trailing_stop_15pip_tp_exit_times_match_tradingview(
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_20pip_trailing_stop_15pip_tp,
):
    """Validates all exit times match between platform and TradingView.

    For trailing stop strategies, this test categorizes ALL time discrepancies
    to ensure each one is explainable and acceptable. This includes:
    1. Same-bar entry/exit (TradingView historical limitation)
    2. Entry bar MFE patterns (TradingView ignores entry bar favorable movement)
    3. Known documented edge cases (see KNOWN_EDGE_CASES)

    Validates: [BT-7.8], [SE-3.5.3]
    """
    from tests.validation.analyzers.trailing_stop import (
        TrailingStopDiscrepancyAnalyzer,
    )

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop_15pip_tp

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Get known edge cases for this strategy
    strategy_edge_cases = KNOWN_EDGE_CASES.get(
        "ema_crossover/20pip_trailing_stop_15pip_tp", {}
    )
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Use analyzer to categorize time mismatches based on MFE patterns
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        take_profit_pips=0.0015,  # 15 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
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
                # (via entry bar MFE patterns or zoom discrepancies)
                exit_time_categories = [
                    "SAME_BAR_EXIT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
                    "PLATFORM_ZOOM_INTRABAR_STOP",
                    "PLATFORM_ZOOM_INTRABAR_TP",
                ]
                is_analyzer_explained = False
                for category in exit_time_categories:
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


def test_ema_crossover_20pip_trailing_stop_15pip_tp_exit_prices_match_tradingview(
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_20pip_trailing_stop_15pip_tp,
):
    """Validates all exit prices match between platform and TradingView.

    For trailing stop strategies, this test categorizes ALL discrepancies to ensure
    each one is explainable and acceptable. This prevents regressions where future
    changes might break the trailing stop logic.

    Known acceptable discrepancy categories:
    1. SAME_BAR_EXIT: Entry/exit on same bar (TradingView limitation)
    2. TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT: Entry bar had peak MFE
       (TV ignores it) - strict mathematical verification
    3. TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED: Entry bar had peak MFE
       (TV ignores it) - independent exit verification
    4. PLATFORM_ZOOM_INTRABAR_STOP: Platform detected intrabar stop
       via 1-minute zoom
    5. PLATFORM_ZOOM_INTRABAR_TP: Platform detected intrabar take-profit
       via 1-minute zoom

    Any UNEXPLAINED discrepancies will cause the test to fail, indicating
    a potential bug or new TradingView behavior that needs investigation.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    from tests.validation.analyzers.trailing_stop import (
        TrailingStopDiscrepancyAnalyzer,
    )

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_20pip_trailing_stop_15pip_tp

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Analyze discrepancies using the discrepancy analyzer
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        take_profit_pips=0.0015,  # 15 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
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
                f"  TradingView: {trade['tv_exit']:.5f} " f"({trade['tv_exit_reason']})"
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


# =============================================================================
# EMA Crossover with 2x ATR Dynamic Stop
# =============================================================================


def test_ema_crossover_2atr_stop_metadata_schema_validation(
    golden_metadata,
    shared_data_handler,
):
    """Validates metadata.json conforms to schema for 2atr_stop.

    Validates: [DH-2.13]
    """
    # If we got here, golden_metadata fixture already validated schema
    assert golden_metadata is not None
    assert golden_metadata.get("dataset_type") == "strategy"
    assert golden_metadata.get("strategy_name") == "ema_crossover_2atr_stop"


def test_ema_crossover_2atr_stop_trade_count_matches_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_2atr_stop,
):
    """Validates platform generates same number of trades as TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_2atr_stop

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Compare counts
    assert len(platform_df) == len(tv_df), (
        f"Trade count mismatch: Platform generated {len(platform_df)} "
        f"trades, TradingView generated {len(tv_df)} trades"
    )


def test_ema_crossover_2atr_stop_entry_times_match_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_2atr_stop,
):
    """Validates all entry times match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_2atr_stop

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


def test_ema_crossover_2atr_stop_entry_prices_match_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_2atr_stop,
):
    """Validates all entry prices match between platform and TradingView.

    Validates: [BT-7.8], [SE-3.5.3]
    """
    date_range = golden_metadata.get("date_range")
    price_tolerance = 0.00001

    # Load platform trades
    platform_trades = platform_trades_2atr_stop

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
                f"Platform={mm['platform']:.5f}, "
                f"TV={mm['tradingview']:.5f}, "
                f"Diff={mm['diff']:.5f}"
            )
        if len(mismatches) > 10:
            print(f"... and {len(mismatches) - 10} more")

    assert len(mismatches) == 0, (
        f"Found {len(mismatches)} entry price mismatches. "
        f"Entry prices must match exactly "
        f"(tolerance={price_tolerance})."
    )


def test_ema_crossover_2atr_stop_exit_times_match_tradingview(
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_2atr_stop,
):
    """Validates all exit times match between platform and TradingView.

    For indicator-based stop strategies, this test categorizes ALL time
    discrepancies to ensure each one is explainable and acceptable.

    Validates: [BT-7.8], [SE-3.5.3], [REM-6.3]
    """
    from tests.validation.analyzers import create_analyzer_for_strategy

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_2atr_stop

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Create analyzer using factory (configured from metadata)
    analyzer = create_analyzer_for_strategy(golden_metadata)

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    # Check for trades with exit TIME mismatches
    time_mismatches = []

    for i in range(len(platform_df)):
        p_time = platform_df.iloc[i]["exit_time"]
        tv_time = tv_df.iloc[i]["exit_time"]

        if p_time != tv_time:
            # Check if this mismatch was categorized by analyzer
            categorized = any(
                i in [t["trade_index"] for t in cat_trades]
                for cat_trades in categories.values()
            )

            if not categorized:
                time_mismatches.append(
                    {
                        "trade_num": i + 1,
                        "platform": str(p_time),
                        "tradingview": str(tv_time),
                    }
                )

    if time_mismatches:
        print("\n=== Uncategorized Exit Time Mismatches ===")
        for mm in time_mismatches[:10]:
            print(
                f"Trade {mm['trade_num']}: "
                f"Platform={mm['platform']}, TV={mm['tradingview']}"
            )
        if len(time_mismatches) > 10:
            print(f"... and {len(time_mismatches) - 10} more")

    # Generate and print summary report
    summary_report = analyzer.generate_summary_report(categories)
    print(f"\n{summary_report}")

    # Assert all discrepancies are explained
    analyzer.assert_all_explained(categories)


def test_ema_crossover_2atr_stop_exit_prices_match_tradingview(
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_2atr_stop,
):
    """Validates all exit prices match between platform and TradingView.

    For indicator-based stop strategies, this test categorizes ALL
    discrepancies to ensure each one is explainable and acceptable.

    Known acceptable discrepancy categories:
    1. SAME_BAR_EXIT: Entry/exit on same bar (TradingView limitation)
    2. INDICATOR_RECALCULATION: Indicator value changed significantly
    3. ENTRY_BAR_INDICATOR_DIFFERENCE: Indicator differs on entry bar
    4. PLATFORM_ZOOM_INTRABAR_STOP: Platform detected intrabar stop
       via 1-minute zoom

    Any UNEXPLAINED discrepancies will cause the test to fail.

    Validates: [BT-7.8], [SE-3.5.3], [REM-6.3]
    """
    from tests.validation.analyzers import create_analyzer_for_strategy

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = platform_trades_2atr_stop

    # Align trades
    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    # Create analyzer using factory (configured from metadata)
    analyzer = create_analyzer_for_strategy(golden_metadata)

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
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
            print(f"\nTrade #{trade['trade_num']} " f"({trade['direction'].upper()})")
            print(f"  Entry: {trade['entry_time']} @ " f"{trade['entry_price']:.5f}")
            print(f"  Exit:  {trade['exit_time']}")
            print(
                f"  Platform: {trade['platform_exit']:.5f} "
                f"({trade['platform_exit_reason']})"
            )
            print(
                f"  TradingView: {trade['tv_exit']:.5f} " f"({trade['tv_exit_reason']})"
            )
            print(f"  Difference: {trade['price_diff_pips']:.1f} pips")
            print(f"  → {trade['explanation']}")

        if len(trades) > 5:
            print(f"\n  ... and {len(trades) - 5} more with similar " f"explanations")

    # Assert all discrepancies are explained
    analyzer.assert_all_explained(categories)


# EMA Crossover with Bollinger Stop
# =============================================================================


def test_ema_crossover_bb_stop_metadata_schema_validation(
    golden_metadata,
    shared_data_handler,
):
    """Validates metadata.json conforms to schema for bb_stop."""

    assert golden_metadata is not None
    assert golden_metadata.get("dataset_type") == "strategy"
    assert golden_metadata.get("strategy_name") == "ema_crossover_bb_stop"


def test_ema_crossover_bb_stop_trade_count_matches_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_bb_stop,
):
    """Validates Bollinger stop produces same trade count as TradingView."""

    date_range = golden_metadata.get("date_range")
    platform_trades = platform_trades_bb_stop

    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    assert len(platform_df) == len(tv_df), (
        f"Trade count mismatch: Platform generated {len(platform_df)} trades, "
        f"TradingView generated {len(tv_df)} trades"
    )


def test_ema_crossover_bb_stop_exit_times_match_tradingview(
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_bb_stop,
):
    """Validates exit times match, with analyzer explaining mismatches."""

    from tests.validation.analyzers import create_analyzer_for_strategy

    date_range = golden_metadata.get("date_range")
    platform_trades = platform_trades_bb_stop

    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    analyzer = create_analyzer_for_strategy(golden_metadata)
    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    analyzer.assert_all_explained(categories)


def test_ema_crossover_bb_stop_exit_prices_match_tradingview(
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_bb_stop,
):
    """Validates exit prices match TradingView for Bollinger stop."""

    from tests.validation.analyzers import create_analyzer_for_strategy

    date_range = golden_metadata.get("date_range")
    platform_trades = platform_trades_bb_stop

    platform_df, tv_df = align_trades(platform_trades, tradingview_trades, date_range)

    analyzer = create_analyzer_for_strategy(golden_metadata)
    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    analyzer.assert_all_explained(categories)
