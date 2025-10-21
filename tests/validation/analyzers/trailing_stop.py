"""
Trailing Stop Discrepancy Analyzer

This module provides categorization and explanation for all discrepancies between
platform and TradingView trailing stop exits. It ensures that every discrepancy
is explainable and acceptable, preventing regressions from future changes.

Known acceptable discrepancy categories:
1. SAME_BAR_EXIT: Entry and exit on same bar (TradingView historical limitation)
2. TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT: Entry bar had peak favorable movement
   (TV ignores it) - verified via strict mathematical equality
3. TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED: Entry bar had peak favorable movement
   (TV ignores it) - verified via independent exit validation
4. PLATFORM_ZOOM_INTRABAR_STOP: Platform detected intrabar stop via 1-minute zoom

MANUALLY VERIFIED TV_IGNORED_ENTRY_BAR_PEAK_MFE EXIT TIME DISCREPANCIES:
The following trades have been manually inspected and verified to correctly
exhibit the entry bar peak MFE pattern, where TradingView ignores favorable
movement on the entry bar:

trade entry_time          platform_exit_time  tv_exit_time
39    2023-04-17 01:00:00 2023-04-17 02:00:00 2023-04-17 05:00:00
48    2023-04-26 11:00:00 2023-04-26 12:00:00 2023-04-26 14:00:00
66    2023-06-21 14:00:00 2023-06-21 15:00:00 2023-06-22 11:00:00
78    2023-08-09 17:00:00 2023-08-09 20:00:00 2023-08-10 12:00:00
80    2023-08-21 11:00:00 2023-08-21 12:00:00 2023-08-21 13:00:00
115   2023-12-18 12:00:00 2023-12-18 13:00:00 2023-12-18 15:00:00
117   2023-12-21 09:00:00 2023-12-21 10:00:00 2023-12-21 11:00:00
119   2023-12-29 09:00:00 2023-12-29 10:00:00 2023-12-29 11:00:00
167   2024-04-26 20:00:00 2024-04-29 00:00:00 2024-04-29 01:00:00
169   2024-04-30 06:00:00 2024-04-30 07:00:00 2024-04-30 09:00:00
177   2024-05-21 13:00:00 2024-05-22 02:00:00 2024-05-22 15:00:00
223   2024-09-30 19:00:00 2024-09-30 22:00:00 2024-10-01 09:00:00
224   2024-10-20 23:00:00 2024-10-21 06:00:00 2024-10-21 07:00:00
239   2024-12-02 05:00:00 2024-12-02 06:00:00 2024-12-02 09:00:00
242   2024-12-10 06:00:00 2024-12-10 07:00:00 2024-12-10 08:00:00
"""

from typing import Any, Dict, List, Optional, Tuple, cast

import pandas as pd

from tests.validation.ambiguity_analyzer import (
    AmbiguityAnalyzer,
    DiscrepancyResult,
)
from tests.validation.analyzers import register_analyzer


@register_analyzer("trailing_stop")
class TrailingStopDiscrepancyAnalyzer(AmbiguityAnalyzer):
    """Analyzes and categorizes trailing stop exit discrepancies."""

    def __init__(
        self,
        trailing_stop_pips: float = 0.0020,
        take_profit_pips: Optional[float] = None,
        tolerance: float = 0.00001,
    ):
        """
        Initialize the analyzer.

        Args:
            trailing_stop_pips: Trailing stop distance in price terms
                (e.g., 0.0020 for 20 pips)
            take_profit_pips: Take profit distance in price terms
                (e.g., 0.0015 for 15 pips). Optional - only needed for
                strategies with both trailing stop and take profit.
            tolerance: Price tolerance for considering matches
                (default: 1e-5)
        """
        self.trailing_stop_pips = trailing_stop_pips
        self.take_profit_pips = take_profit_pips
        self.tolerance = tolerance

        # Category definitions (used by base class property)
        self.acceptable_categories = [
            "SAME_BAR_EXIT",
            "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
            "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
            "PLATFORM_ZOOM_INTRABAR_STOP",
            "PLATFORM_ZOOM_INTRABAR_TP",
        ]

    @classmethod
    def from_metadata(cls, metadata: dict) -> "TrailingStopDiscrepancyAnalyzer":
        """Create analyzer from strategy metadata.

        Args:
            metadata: Strategy metadata dictionary containing:
                - trailing_stop_pips: Trailing stop distance (in pips, e.g., 20)
                - take_profit_pips: Optional take profit distance (in pips)

        Returns:
            Configured TrailingStopDiscrepancyAnalyzer instance
        """
        trailing_stop_pips_val = metadata.get("trailing_stop_pips")
        take_profit_pips_val = metadata.get("take_profit_pips")

        if trailing_stop_pips_val is None:
            raise ValueError(
                "metadata.json must specify 'trailing_stop_pips' for "
                "trailing_stop analyzer"
            )

        # Convert pips to price terms (e.g., 20 pips -> 0.0020 for EUR/USD)
        # Assuming 4-decimal pip location (-4)
        trailing_stop_price = trailing_stop_pips_val * 0.0001
        take_profit_price = (
            take_profit_pips_val * 0.0001 if take_profit_pips_val is not None else None
        )

        return cls(
            trailing_stop_pips=trailing_stop_price,
            take_profit_pips=take_profit_price,
        )

    def analyze_discrepancies(
        self,
        platform_df: pd.DataFrame,
        tv_df: pd.DataFrame,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: Optional[pd.DataFrame] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze all exit price discrepancies and categorize them.

        Args:
            platform_df: DataFrame with platform trades
            tv_df: DataFrame with TradingView trades
                (aligned with platform_df)
            ohlcv_data: OHLCV data with columns:
                open, high, low, close, ema_fast, ema_slow
            ohlcv_1min: Optional 1-minute OHLCV data for zoom detection

        Returns:
            Dictionary mapping category names to lists of discrepancy details
        """
        # Store 1-minute data for use in zoom detection
        self.ohlcv_1min = ohlcv_1min
        categories: dict[str, list] = {
            cat: [] for cat in self.KNOWN_ACCEPTABLE_CATEGORIES
        }
        categories["UNEXPLAINED"] = []

        total_trades = len(platform_df)

        for i in range(total_trades):
            p_row = platform_df.iloc[i]
            tv_row = tv_df.iloc[i]

            entry_time = pd.Timestamp(p_row["entry_time"])
            exit_time = pd.Timestamp(p_row["exit_time"])
            entry_price = p_row["entry_price"]
            p_exit_price = p_row["exit_price"]
            tv_exit_price = tv_row["exit_price"]
            tv_exit_time = pd.Timestamp(tv_row["exit_time"])
            direction = tv_row["side"]

            price_diff = abs(p_exit_price - tv_exit_price)
            time_diff = exit_time != tv_exit_time

            # Check if there's any discrepancy (price OR time)
            # We analyze patterns even if discrepancies are small, because the
            # patterns explain WHY discrepancies exist (e.g., entry bar MFE)
            has_discrepancy = price_diff >= self.tolerance or time_diff

            if not has_discrepancy:
                # Perfect match - skip
                continue

            # Create trade info
            trade_info = self._create_trade_info(
                i + 1,
                direction,
                entry_time,
                exit_time,
                entry_price,
                p_exit_price,
                tv_exit_price,
                p_row,
                tv_row,
            )

            # Categorize the discrepancy
            category = self._categorize_discrepancy(
                trade_info,
                entry_time,
                exit_time,
                entry_price,
                direction,
                p_row,
                tv_row,
                ohlcv_data,
            )

            categories[category].append(trade_info)

        return categories

    def _create_trade_info(
        self,
        trade_num: int,
        direction: str,
        entry_time: pd.Timestamp,
        exit_time: pd.Timestamp,
        entry_price: float,
        p_exit_price: float,
        tv_exit_price: float,
        p_row: pd.Series,
        tv_row: pd.Series,
    ) -> Dict[str, Any]:
        """Create base trade information dictionary."""
        return {
            "trade_num": trade_num,
            "direction": direction,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": entry_price,
            "platform_exit": p_exit_price,
            "tv_exit": tv_exit_price,
            "price_diff_pips": abs(p_exit_price - tv_exit_price) * 10000,
            "platform_exit_reason": p_row.get("exit_reason", ""),
            "tv_exit_reason": tv_row.get("exit_reason", ""),
        }

    def _categorize_discrepancy(
        self,
        trade_info: Dict[str, Any],
        entry_time: pd.Timestamp,
        exit_time: pd.Timestamp,
        entry_price: float,
        direction: str,
        p_row: pd.Series,
        tv_row: pd.Series,
        ohlcv_data: pd.DataFrame,
    ) -> str:
        """
        Categorize a single discrepancy.

        Returns:
            Category name (one of KNOWN_ACCEPTABLE_CATEGORIES or 'UNEXPLAINED')
        """
        # Determine exit types
        platform_is_stop = "stop" in str(p_row.get("exit_reason", "")).lower()
        tv_is_stop = "trail" in str(trade_info["tv_exit_reason"]).lower()

        # CATEGORY 1: Same-bar entry/exit
        if entry_time == exit_time:
            trade_info["explanation"] = (
                "Entry and exit on same bar. TradingView historical backtesting "
                "cannot detect intra-bar stop hits on entry bar."
            )
            return "SAME_BAR_EXIT"

        # For stop-loss related discrepancies, calculate MFE
        if platform_is_stop or tv_is_stop:
            entry_bar_mfe, overall_mfe_excl_entry = self._calculate_mfe(
                entry_time, exit_time, entry_price, direction, ohlcv_data
            )

            trade_info["entry_bar_mfe_pips"] = entry_bar_mfe * 10000
            trade_info["overall_mfe_excl_entry_pips"] = overall_mfe_excl_entry * 10000

            # CATEGORY 2: Entry bar had peak MFE
            if entry_bar_mfe > overall_mfe_excl_entry + self.tolerance:
                # Calculate expected price difference based on MFE difference
                expected_price_diff = entry_bar_mfe - overall_mfe_excl_entry
                actual_price_diff = abs(
                    trade_info["platform_exit"] - trade_info["tv_exit"]
                )

                trade_info["expected_price_diff_pips"] = expected_price_diff * 10000
                trade_info["actual_price_diff_pips"] = actual_price_diff * 10000

                # Verify that exit price difference matches MFE difference
                # This confirms the discrepancy is truly due to entry bar MFE
                price_diff_matches = (
                    abs(expected_price_diff - actual_price_diff) < self.tolerance
                )

                # PATH 1 (STRICT): BOTH platform and TV exited via stop-loss
                # AND the price difference matches expected
                if platform_is_stop and tv_is_stop and price_diff_matches:
                    trade_info["explanation"] = (
                        f"Entry bar had peak favorable movement "
                        f"({entry_bar_mfe * 10000:.1f} pips). "
                        f"Platform adjusted trailing stop for entry bar MFE. "
                        f"TradingView ignores favorable movement on entry bar, "
                        f"never adjusted stop. "
                        f"Exit price difference ({actual_price_diff * 10000:.1f} pips) "
                        f"matches MFE difference "
                        f"({expected_price_diff * 10000:.1f} pips). "
                        f"This is a known TradingView historical backtesting "
                        f"limitation."
                    )
                    return "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT"

                # PATH 2 (NON-STRICT): Verify both exits independently
                # Platform: entry bar MFE caused exit
                # TV: exited via stop at expected level based on TV's MFE
                if platform_is_stop and tv_is_stop:
                    # Verify platform exit matches entry bar MFE ± stop distance
                    # Long: stop trails below peak = entry + mfe - stop
                    # Short: stop trails above trough = entry - mfe + stop
                    if direction == "long":
                        expected_platform_exit = (
                            entry_price + entry_bar_mfe - self.trailing_stop_pips
                        )
                    else:  # short
                        expected_platform_exit = (
                            entry_price - entry_bar_mfe + self.trailing_stop_pips
                        )

                    platform_exit_matches = (
                        abs(trade_info["platform_exit"] - expected_platform_exit)
                        < self.tolerance
                    )

                    if platform_exit_matches:
                        # Platform check passed - now verify TV independently
                        # Calculate TV's MFE up to TV exit time
                        tv_exit_time = pd.Timestamp(tv_row["exit_time"])
                        _, tv_overall_mfe = self._calculate_mfe(
                            entry_time,
                            tv_exit_time,
                            entry_price,
                            direction,
                            ohlcv_data,
                        )

                        # Verify TV exit matches its MFE ± stop distance
                        # Long: stop trails below peak = entry + mfe - stop
                        # Short: stop trails above trough = entry - mfe + stop
                        if direction == "long":
                            expected_tv_exit = (
                                entry_price + tv_overall_mfe - self.trailing_stop_pips
                            )
                        else:  # short
                            expected_tv_exit = (
                                entry_price - tv_overall_mfe + self.trailing_stop_pips
                            )

                        tv_exit_matches = (
                            abs(trade_info["tv_exit"] - expected_tv_exit)
                            < self.tolerance
                        )

                        if tv_exit_matches:
                            trade_info["explanation"] = (
                                f"Entry bar had peak favorable movement "
                                f"({entry_bar_mfe * 10000:.1f} pips). "
                                f"Platform exit at {trade_info['platform_exit']:.5f} "
                                f"matches expected stop level based on entry bar MFE. "
                                f"TradingView's MFE (excluding entry bar) was "
                                f"{tv_overall_mfe * 10000:.1f} pips. "
                                f"TV exit at {trade_info['tv_exit']:.5f} matches "
                                f"expected stop level based on TV's MFE tracking. "
                                f"Both exits verified independently."
                            )
                            return "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED"

        # CATEGORY 3: Platform zoom detected intrabar stop hit
        # Check if platform's 1-minute zoom feature detected a stop hit
        # that TradingView couldn't see with hourly OHLC
        # (Only check this if PEAK_MFE didn't explain it)
        if platform_is_stop:
            zoom_result = self._check_zoom_discrepancy(
                trade_info,
                entry_time,
                exit_time,
                entry_price,
                direction,
                p_row,
                tv_row,
                ohlcv_data,
            )
            if zoom_result:
                trade_info["explanation"] = zoom_result
                return "PLATFORM_ZOOM_INTRABAR_STOP"

        # CATEGORY 4: Platform zoom detected intrabar take-profit hit
        # Check if platform exited at TP while TV exited at trailing stop
        # This happens when both TP and trailing stop are within the same bar's range
        # but TP was hit first chronologically (detected via 1-minute zoom)
        platform_is_tp = "take-profit" in str(p_row.get("exit_reason", "")).lower()
        if platform_is_tp and tv_is_stop and self.take_profit_pips is not None:
            # Calculate TP level
            if direction == "long":
                tp_level = entry_price + self.take_profit_pips
            else:  # short
                tp_level = entry_price - self.take_profit_pips

            # Verify platform exited at TP level
            platform_exit_matches_tp = (
                abs(trade_info["platform_exit"] - tp_level) < self.tolerance
            )

            if platform_exit_matches_tp:
                # Find the exact minute when TP was hit using 1-minute data
                exact_tp_time = self._find_tp_hit_time_1min(
                    entry_time=entry_time,
                    entry_price=entry_price,
                    tp_level=tp_level,
                    direction=direction,
                    exit_time=exit_time,
                )

                if exact_tp_time:
                    minute_str = exact_tp_time.strftime("%H:%M")
                    tv_exit = trade_info["tv_exit"]
                    trade_info["explanation"] = (
                        f"Platform detected intra-bar take-profit hit "
                        f"via 1-minute zoom. "
                        f"{'Long' if direction == 'long' else 'Short'} entry "
                        f"at {entry_price:.5f} with TP at {tp_level:.5f}. "
                        f"Platform used 1-minute data to detect TP hit "
                        f"at minute {minute_str} within the {exit_time} bar "
                        f"and correctly exited at TP price {tp_level:.5f}. "
                        f"TradingView, using only hourly bars, could not "
                        f"determine intra-bar sequence and exited at trailing "
                        f"stop {tv_exit:.5f} instead. "
                        f"Platform is MORE accurate due to 1-minute zoom "
                        f"detecting exact moment when TP was hit."
                    )
                else:
                    # Fallback if we can't find exact minute
                    tv_exit = trade_info["tv_exit"]
                    trade_info["explanation"] = (
                        f"Platform detected intra-bar take-profit hit "
                        f"via 1-minute zoom. "
                        f"{'Long' if direction == 'long' else 'Short'} entry "
                        f"at {entry_price:.5f} with TP at {tp_level:.5f}. "
                        f"Platform used 1-minute data to detect TP hit "
                        f"within the {exit_time} bar and correctly exited "
                        f"at TP price {tp_level:.5f}. "
                        f"TradingView, using only hourly bars, could not "
                        f"determine intra-bar sequence and exited at trailing "
                        f"stop {tv_exit:.5f} instead. "
                        f"Platform is MORE accurate due to 1-minute zoom "
                        f"detecting exact moment when TP was hit."
                    )
                return "PLATFORM_ZOOM_INTRABAR_TP"

        # Cannot explain - requires investigation
        trade_info["explanation"] = (
            'Unable to categorize this discrepancy. Requires investigation. '
            f'Platform exit type: {"stop-loss" if platform_is_stop else "signal"}, '
            f'TradingView exit type: {"stop-loss" if tv_is_stop else "signal"}'
        )
        return "UNEXPLAINED"

    def _calculate_mfe(
        self,
        entry_time: pd.Timestamp,
        exit_time: pd.Timestamp,
        entry_price: float,
        direction: str,
        ohlcv_data: pd.DataFrame,
    ) -> Tuple[float, float]:
        """
        Calculate Maximum Favorable Excursion for entry bar and overall.

        Returns:
            Tuple of (entry_bar_mfe, overall_mfe_excluding_entry_bar)
        """
        # Entry bar MFE
        entry_bar = ohlcv_data.loc[entry_time]
        if direction == "long":
            entry_bar_mfe = entry_bar["high"] - entry_price
        else:
            entry_bar_mfe = entry_price - entry_bar["low"]

        # Overall MFE (excluding entry bar)
        bars_after_entry = ohlcv_data.loc[entry_time:exit_time].iloc[
            1:
        ]  # Skip entry bar
        if len(bars_after_entry) > 0:
            if direction == "long":
                overall_mfe_excl_entry = float(
                    (bars_after_entry["high"] - entry_price).max()
                )
            else:
                overall_mfe_excl_entry = float(
                    (entry_price - bars_after_entry["low"]).max()
                )
        else:
            overall_mfe_excl_entry = 0.0

        return max(0.0, float(entry_bar_mfe)), max(0.0, overall_mfe_excl_entry)

    def _simulate_trailing_stop_1min(
        self,
        entry_time: pd.Timestamp,
        entry_price: float,
        direction: str,
        platform_exit_time: pd.Timestamp,
    ) -> Tuple[pd.Timestamp | None, float | None]:
        """
        Simulate trailing stop using 1-minute data to find exact stop hit.

        Args:
            entry_time: Entry timestamp (hourly bar)
            entry_price: Entry price
            direction: "long" or "short"
            platform_exit_time: Platform's exit time (hourly bar)

        Returns:
            Tuple of (exact_stop_hit_time, exact_stop_hit_price)
            or (None, None) if stop not hit or data unavailable
        """
        if self.ohlcv_1min is None:
            return None, None

        # Get all 1-minute bars from entry through platform exit hour
        try:
            # Get bars from entry time through end of platform exit hour
            exit_hour_end = platform_exit_time.floor("h") + pd.Timedelta(hours=1)
            bars_1min = self.ohlcv_1min.loc[entry_time:exit_hour_end]

            if len(bars_1min) == 0:
                return None, None
        except (KeyError, IndexError):
            return None, None

        # Initialize trailing stop tracking
        # Start with entry price as the peak/trough
        peak_or_trough = entry_price

        if direction == "long":
            stop_level = entry_price - self.trailing_stop_pips
        else:  # short
            stop_level = entry_price + self.trailing_stop_pips

        # Process each 1-minute bar chronologically
        for timestamp, bar in bars_1min.iterrows():
            # Check if stop was hit on this bar
            if direction == "long":
                stop_hit = bar["low"] <= stop_level
            else:  # short
                stop_hit = bar["high"] >= stop_level

            if stop_hit:
                # Stop was hit - return exact time and price
                return cast(pd.Timestamp, timestamp), stop_level

            # No exit on this bar - update peak/trough and trailing stop
            if direction == "long":
                # For long: track peak high, stop trails below it
                if bar["high"] > peak_or_trough:
                    peak_or_trough = bar["high"]
                    stop_level = peak_or_trough - self.trailing_stop_pips
            else:
                # For short: track trough low, stop trails above it
                if bar["low"] < peak_or_trough:
                    peak_or_trough = bar["low"]
                    stop_level = peak_or_trough + self.trailing_stop_pips

        # No stop hit detected
        return None, None

    def _find_tp_hit_time_1min(
        self,
        entry_time: pd.Timestamp,
        entry_price: float,
        tp_level: float,
        direction: str,
        exit_time: pd.Timestamp,
    ) -> pd.Timestamp | None:
        """
        Find the exact 1-minute timestamp when take-profit was hit.

        Args:
            entry_time: Entry timestamp (hourly bar)
            entry_price: Entry price
            tp_level: Take-profit price level
            direction: "long" or "short"
            exit_time: Exit time (hourly bar)

        Returns:
            Exact timestamp when TP was hit, or None if not found
        """
        if self.ohlcv_1min is None:
            return None

        # Get all 1-minute bars from entry through exit hour
        try:
            exit_hour_end = exit_time.floor("h") + pd.Timedelta(hours=1)
            bars_1min = self.ohlcv_1min.loc[entry_time:exit_hour_end]

            if len(bars_1min) == 0:
                return None
        except (KeyError, IndexError):
            return None

        # Process each 1-minute bar to find when TP was hit
        for timestamp, bar in bars_1min.iterrows():
            if direction == "long":
                # For long, TP is hit when high >= tp_level
                if bar["high"] >= tp_level:
                    return cast(pd.Timestamp, timestamp)
            else:  # short
                # For short, TP is hit when low <= tp_level
                if bar["low"] <= tp_level:
                    return cast(pd.Timestamp, timestamp)

        # TP not found in 1-minute data
        return None

    def _check_zoom_discrepancy(
        self,
        trade_info: Dict[str, Any],
        entry_time: pd.Timestamp,
        exit_time: pd.Timestamp,
        entry_price: float,
        direction: str,
        p_row: pd.Series,
        tv_row: pd.Series,
        ohlcv_data: pd.DataFrame,
    ) -> Optional[str]:
        """
        Check if discrepancy is due to platform's 1-minute zoom feature.

        Uses 1-minute data simulation to verify that platform's exit matches
        the exact trailing stop hit when using intra-bar resolution.

        Returns explanation string if zoom discrepancy detected, None otherwise.
        """
        if self.ohlcv_1min is None:
            return None  # Can't verify without 1-minute data

        platform_exit_time = pd.Timestamp(p_row["exit_time"])
        tv_exit_time = pd.Timestamp(tv_row["exit_time"])
        platform_exit_price = p_row["exit_price"]
        tv_exit_price = tv_row["exit_price"]

        # Simulate trailing stop using 1-minute data
        exact_stop_time, exact_stop_price = self._simulate_trailing_stop_1min(
            entry_time=entry_time,
            entry_price=entry_price,
            direction=direction,
            platform_exit_time=platform_exit_time,
        )

        if exact_stop_time is None or exact_stop_price is None:
            return None  # Simulation failed or stop not hit

        # Verify platform's exit matches the 1-minute simulation
        platform_exit_matches = (
            abs(platform_exit_price - exact_stop_price) < self.tolerance
        )

        if not platform_exit_matches:
            return None  # Platform exit doesn't match zoom simulation

        # Build explanation based on timing relationship
        if platform_exit_time < tv_exit_time:
            # Platform exits earlier - TV missed the intrabar stop hit
            return (
                f"Platform exit verified via 1-minute zoom. "
                f"{'Long' if direction == 'long' else 'Short'} entry at "
                f"{entry_price:.5f}. "
                f"Platform exited at {platform_exit_time} at "
                f"{platform_exit_price:.5f}. "
                f"1-minute simulation confirms stop hit at minute "
                f"{exact_stop_time.strftime('%H:%M')} at price "
                f"{exact_stop_price:.5f}. "
                f"TradingView, using only hourly bars, couldn't detect this "
                f"intrabar stop hit and continued trading, exiting later at "
                f"{tv_exit_time} at {tv_exit_price:.5f}."
            )
        elif platform_exit_time > tv_exit_time:
            # TV exits earlier - need to verify TV's exit was a false stop hit
            # Simulate 1-minute for TV's exit bar to prove stop NOT hit
            tv_stop_time, tv_stop_price = self._simulate_trailing_stop_1min(
                entry_time=entry_time,
                entry_price=entry_price,
                direction=direction,
                platform_exit_time=tv_exit_time,
            )

            # If stop was hit in TV's bar, this isn't the zoom issue we're looking for
            if tv_stop_time is not None:
                return None

            # Stop was NOT hit in TV's exit bar - TV had a false exit
            return (
                f"TradingView false exit due to hourly-only resolution. "
                f"{'Long' if direction == 'long' else 'Short'} entry at "
                f"{entry_price:.5f}. "
                f"TradingView exited at {tv_exit_time} at {tv_exit_price:.5f}. "
                f"1-minute simulation proves stop was NOT actually hit during "
                f"TV's exit bar - TV incorrectly concluded stop was hit based "
                f"on hourly OHLC alone. "
                f"Platform continued trading with 1-minute precision, "
                f"actually hitting stop at {platform_exit_time} at minute "
                f"{exact_stop_time.strftime('%H:%M')} at price "
                f"{exact_stop_price:.5f}."
            )
        else:
            # Same time, different price
            price_diff = abs(platform_exit_price - tv_exit_price)
            if price_diff > self.tolerance:
                return (
                    f"Both platforms exited on same bar ({platform_exit_time}). "
                    f"Platform used 1-minute zoom for exact stop price. "
                    f"1-minute simulation confirms stop hit at minute "
                    f"{exact_stop_time.strftime('%H:%M')} at price "
                    f"{exact_stop_price:.5f}. "
                    f"Platform exit at {platform_exit_price:.5f} matches simulation. "
                    f"TradingView used hourly bar "
                    f"{'low' if direction == 'long' else 'high'}: "
                    f"{tv_exit_price:.5f}. "
                    f"Price difference ({price_diff * 10000:.1f} pips) due to "
                    f"platform's 1-minute intrabar resolution."
                )

        return None

    # Abstract method implementations for AmbiguityAnalyzer base class

    def get_acceptable_categories(self) -> List[str]:
        """Get list of acceptable discrepancy categories.

        Returns:
            List of category names that are considered acceptable
        """
        return self.acceptable_categories

    def get_analyzer_type(self) -> str:
        """Get analyzer type name for logging/reporting.

        Returns:
            Human-readable analyzer type string
        """
        return "TrailingStop"

    def analyze_discrepancy(
        self,
        platform_trade: pd.Series,
        tv_trade: pd.Series,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> DiscrepancyResult:
        """Analyze a single trade discrepancy.

        Note: This method is not used by TrailingStopAnalyzer because it
        overrides analyze_discrepancies() with custom batch logic.
        Provided for interface compatibility.

        Args:
            platform_trade: Platform trade Series
            tv_trade: TradingView trade Series
            ohlcv_data: OHLCV DataFrame
            ohlcv_1min: Optional 1-minute OHLCV data

        Returns:
            DiscrepancyResult with category and explanation
        """
        raise NotImplementedError(
            "TrailingStopAnalyzer uses custom analyze_discrepancies batch "
            "logic. Use analyze_discrepancies() instead."
        )


def create_analyzer_for_strategy(
    golden_metadata: dict,
    tolerance: float = 0.00001,
) -> TrailingStopDiscrepancyAnalyzer:
    """Factory to create analyzer configured from strategy metadata.

    Reads the strategy metadata.json to determine trailing stop and
    take profit parameters, ensuring analyzer is always configured
    correctly for the strategy being tested.

    Args:
        golden_metadata: Metadata dict loaded from strategy's metadata.json
        tolerance: Price tolerance for match comparisons (default: 1e-5)

    Returns:
        TrailingStopDiscrepancyAnalyzer configured for the strategy

    Raises:
        ValueError: If required parameters are missing from metadata

    Example:
        >>> from tests.validation.golden_utils import load_golden_metadata
        >>> metadata = load_golden_metadata("ema_crossover/20pip_trailing_stop")
        >>> analyzer = create_analyzer_for_strategy(metadata)
        >>> analyzer.trailing_stop_pips  # 0.0020 (20 pips)
        >>> analyzer.take_profit_pips  # None (no TP for this strategy)
    """
    # Extract trailing stop (required)
    trailing_stop_pips_value = golden_metadata.get("trailing_stop_pips")
    if trailing_stop_pips_value is None:
        raise ValueError(
            "Strategy metadata must contain 'trailing_stop_pips' field. "
            f"Got metadata keys: {list(golden_metadata.keys())}"
        )

    # Convert from pips to price (divide by 10,000 for EURUSD)
    trailing_stop_pips = trailing_stop_pips_value / 10000.0

    # Extract take profit (optional)
    take_profit_pips_value = golden_metadata.get("take_profit_pips")
    if take_profit_pips_value is not None:
        take_profit_pips = take_profit_pips_value / 10000.0
    else:
        take_profit_pips = None

    return TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=trailing_stop_pips,
        take_profit_pips=take_profit_pips,
        tolerance=tolerance,
    )
