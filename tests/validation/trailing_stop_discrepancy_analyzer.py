"""
Trailing Stop Discrepancy Analyzer

This module provides categorization and explanation for all discrepancies between
platform and TradingView trailing stop exits. It ensures that every discrepancy
is explainable and acceptable, preventing regressions from future changes.

Known acceptable discrepancy categories:
1. SAME_BAR_EXIT: Entry and exit on same bar (TradingView historical limitation)
2. TV_IGNORED_ENTRY_BAR_PEAK_MFE: Entry bar had peak favorable movement
   (TV ignores it)
"""

from typing import Any, Dict, List, Tuple

import pandas as pd


class TrailingStopDiscrepancyAnalyzer:
    """Analyzes and categorizes trailing stop exit discrepancies."""

    def __init__(self, trailing_stop_pips: float = 0.0020, tolerance: float = 0.00001):
        """
        Initialize the analyzer.

        Args:
            trailing_stop_pips: Trailing stop distance in price terms
                (e.g., 0.0020 for 20 pips)
            tolerance: Price tolerance for considering matches
                (default: 1e-5)
        """
        self.trailing_stop_pips = trailing_stop_pips
        self.tolerance = tolerance

        # Category definitions
        self.KNOWN_ACCEPTABLE_CATEGORIES = [
            "SAME_BAR_EXIT",
            "TV_IGNORED_ENTRY_BAR_PEAK_MFE",
        ]

    def analyze_discrepancies(
        self,
        platform_df: pd.DataFrame,
        tv_df: pd.DataFrame,
        ohlcv_data: pd.DataFrame,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze all exit price discrepancies and categorize them.

        Args:
            platform_df: DataFrame with platform trades
            tv_df: DataFrame with TradingView trades
                (aligned with platform_df)
            ohlcv_data: OHLCV data with columns:
                open, high, low, close, ema_fast, ema_slow

        Returns:
            Dictionary mapping category names to lists of discrepancy details
        """
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
            "tv_exit_signal": tv_row.get("exit_signal", ""),
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
        tv_is_stop = "trail" in str(trade_info["tv_exit_signal"]).lower()

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
                trade_info["explanation"] = (
                    f"Entry bar had peak favorable movement "
                    f"({entry_bar_mfe * 10000:.1f} pips). "
                    f"Platform adjusted trailing stop for entry bar MFE. "
                    f"TradingView ignores favorable movement on entry bar, "
                    f"never adjusted stop. "
                    f"This is a known TradingView historical backtesting "
                    f"limitation."
                )
                return "TV_IGNORED_ENTRY_BAR_PEAK_MFE"

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

    def generate_summary_report(self, categories: Dict[str, List]) -> str:
        """Generate a human-readable summary report."""
        total_discrepancies = sum(len(v) for v in categories.values())
        total_explained = sum(
            len(categories[cat]) for cat in self.KNOWN_ACCEPTABLE_CATEGORIES
        )
        total_unexplained = len(categories["UNEXPLAINED"])

        report = []
        report.append("=" * 100)
        report.append("TRAILING STOP VALIDATION - DISCREPANCY ANALYSIS")
        report.append("=" * 100)
        report.append(f"\nTotal discrepancies: {total_discrepancies}")
        report.append(f"Explained (acceptable): {total_explained}")
        report.append(f"Unexplained (requires investigation): {total_unexplained}")

        if total_unexplained == 0:
            report.append(
                f"\n✓ PASS: All {total_discrepancies} discrepancies are "
                f"explained and acceptable"
            )
            report.append("\nBreakdown:")
            for cat in self.KNOWN_ACCEPTABLE_CATEGORIES:
                if len(categories[cat]) > 0:
                    report.append(f"  - {cat}: {len(categories[cat])}")
        else:
            report.append(f"\n✗ FAIL: {total_unexplained} unexplained discrepancies")
            report.append("\nUnexplained trades:")
            for trade in categories["UNEXPLAINED"]:
                report.append(
                    f"  - Trade #{trade['trade_num']}: {trade['direction']} "
                    f"({trade['price_diff_pips']:.1f} pips difference)"
                )

        report.append("=" * 100)
        return "\n".join(report)

    def assert_all_explained(self, categories: Dict[str, List]):
        """
        Assert that all discrepancies are explained.

        Raises:
            AssertionError: If there are unexplained discrepancies
        """
        unexplained = categories["UNEXPLAINED"]
        if len(unexplained) > 0:
            unexplained_trades = [t["trade_num"] for t in unexplained]
            raise AssertionError(
                f"Found {len(unexplained)} unexplained trailing stop "
                f"discrepancies. "
                f"All discrepancies must be categorized as acceptable. "
                f"Unexplained trades: {unexplained_trades}. "
                f"This may indicate a bug in the platform or a new "
                f"TradingView behavior."
            )
