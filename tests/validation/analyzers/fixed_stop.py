"""
Analyzer for fixed stop-loss and take-profit exit mechanisms.

This analyzer handles strategies with fixed pip-based stop-loss and/or take-profit
levels. It categorizes discrepancies between platform and TradingView exports,
including cases where intrabar ambiguity requires 1-minute resolution zoom.

Categories:
- SAME_BAR_EXIT: Entry and exit occur on the same bar
- PLATFORM_ZOOM_INTRABAR_STOP: Platform zoomed to 1-min and found stop hit first
- PLATFORM_ZOOM_INTRABAR_TP: Platform zoomed to 1-min and found TP hit first
- ZOOM_1MIN_TIE_BREAK: Both hit on same 1-min bar, tie_break_policy applied
"""

from __future__ import annotations

import pandas as pd

from tests.validation.analyzers import register_analyzer


@register_analyzer("fixed_stop")
class FixedStopTPAnalyzer:
    """Analyzer for fixed stop-loss and take-profit strategies."""

    def __init__(
        self,
        stop_loss_pips: float | None = None,
        take_profit_pips: float | None = None,
        pip_size: float = 0.0001,
    ):
        """
        Initialize the FixedStopTPAnalyzer.

        Args:
            stop_loss_pips: Stop loss distance in price terms
                (e.g., 0.0020 for 20 pips)
            take_profit_pips: Take profit distance in price terms
                (e.g., 0.0040 for 40 pips)
            pip_size: Size of one pip in price terms
                (default 0.0001 for EUR/USD)
        """
        self.stop_loss_pips = stop_loss_pips
        self.take_profit_pips = take_profit_pips
        self.pip_size = pip_size

    @classmethod
    def from_metadata(cls, metadata: dict) -> FixedStopTPAnalyzer:
        """Create analyzer from strategy metadata."""
        stop_loss_pips_val = metadata.get("stop_loss_pips")
        take_profit_pips_val = metadata.get("take_profit_pips")

        # At least one must be specified
        if stop_loss_pips_val is None and take_profit_pips_val is None:
            raise ValueError(
                "metadata.json must specify at least one of 'stop_loss_pips' or "
                "'take_profit_pips' for fixed_stop analyzer"
            )

        # Convert pips to price terms (e.g., 20 pips -> 0.0020 for EUR/USD)
        pip_size = 0.0001  # Default for EUR/USD
        stop_loss_price = (
            stop_loss_pips_val * pip_size if stop_loss_pips_val is not None else None
        )
        take_profit_price = (
            take_profit_pips_val * pip_size
            if take_profit_pips_val is not None
            else None
        )

        return cls(
            stop_loss_pips=stop_loss_price,
            take_profit_pips=take_profit_price,
            pip_size=pip_size,
        )

    def analyze_discrepancies(
        self,
        platform_df: pd.DataFrame,
        tv_df: pd.DataFrame,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: pd.DataFrame | None = None,
    ) -> dict[str, list[int]]:
        """
        Analyze exit price/time discrepancies for fixed stop/TP strategies.

        Args:
            platform_df: Platform backtest results
            tv_df: TradingView export results
            ohlcv_data: OHLC price data
            ohlcv_1min: Optional 1-minute OHLC data (unused for fixed stops)

        Returns:
            Dictionary mapping category names to lists of trade indices
        """
        categorized: dict[str, list] = {
            "SAME_BAR_EXIT": [],
            "PLATFORM_ZOOM_INTRABAR_STOP": [],
            "PLATFORM_ZOOM_INTRABAR_TP": [],
            "ZOOM_1MIN_TIE_BREAK": [],
        }
        categorized["UNEXPLAINED"] = []

        total_trades = len(platform_df)

        for i in range(total_trades):
            p_row = platform_df.iloc[i]
            tv_row = tv_df.iloc[i]
            # Check if exit prices or times differ
            entry_time = pd.Timestamp(p_row["entry_time"])
            exit_time_platform = pd.Timestamp(p_row["exit_time"])
            exit_time_tv = pd.Timestamp(tv_row["exit_time"])
            entry_price = p_row["entry_price"]
            exit_price_platform = p_row["exit_price"]
            exit_price_tv = tv_row["exit_price"]
            side = p_row["side"]

            exit_price_differs = abs(exit_price_platform - exit_price_tv) > 1e-6
            exit_time_differs = exit_time_platform != exit_time_tv

            if not (exit_price_differs or exit_time_differs):
                continue  # No discrepancy

            # Build trade details dict
            trade_details = {
                "trade_num": i + 1,
                "entry_time": entry_time,
                "exit_time_platform": exit_time_platform,
                "exit_time_tv": exit_time_tv,
                "entry_price": entry_price,
                "exit_price_platform": exit_price_platform,
                "exit_price_tv": exit_price_tv,
                "side": side,
            }

            # Category 1: Same bar exit (entry and exit on same bar)
            if entry_time == exit_time_platform or entry_time == exit_time_tv:
                categorized["SAME_BAR_EXIT"].append(trade_details)
                continue

            # Get the exit bar for analysis
            exit_bar_time = exit_time_platform
            if exit_bar_time not in ohlcv_data.index:
                # Fall back to TV exit time if platform time not in data
                exit_bar_time = exit_time_tv
                if exit_bar_time not in ohlcv_data.index:
                    categorized["UNEXPLAINED"].append(trade_details)
                    continue  # Can't analyze without bar data

            exit_bar = ohlcv_data.loc[exit_bar_time]

            # Calculate stop and TP levels
            sl_price = None
            tp_price = None

            if side == "long":
                if self.stop_loss_pips is not None:
                    sl_price = entry_price - self.stop_loss_pips
                if self.take_profit_pips is not None:
                    tp_price = entry_price + self.take_profit_pips
            else:  # short
                if self.stop_loss_pips is not None:
                    sl_price = entry_price + self.stop_loss_pips
                if self.take_profit_pips is not None:
                    tp_price = entry_price - self.take_profit_pips

            # Check if both levels are in the bar's range (ambiguous)
            ambiguous = False
            if sl_price is not None and tp_price is not None:
                if side == "long":
                    sl_in_range = exit_bar["low"] <= sl_price <= exit_bar["high"]
                    tp_in_range = exit_bar["low"] <= tp_price <= exit_bar["high"]
                    ambiguous = sl_in_range and tp_in_range
                else:  # short
                    sl_in_range = exit_bar["low"] <= sl_price <= exit_bar["high"]
                    tp_in_range = exit_bar["low"] <= tp_price <= exit_bar["high"]
                    ambiguous = sl_in_range and tp_in_range

            if not ambiguous:
                # If not ambiguous, this shouldn't cause a discrepancy
                # (unless there's a different issue)
                categorized["UNEXPLAINED"].append(trade_details)
                continue

            # Ambiguous case - platform should have zoomed to 1-minute
            # Determine which exit occurred based on platform's exit reason
            platform_reason = p_row.get("exit_reason", "")
            tv_reason = tv_row.get("exit_reason", "")

            # Category 2 & 3: Platform zoomed and found stop or TP first
            if platform_reason == "stop-loss" and tv_reason == "take-profit":
                categorized["PLATFORM_ZOOM_INTRABAR_STOP"].append(trade_details)
            elif platform_reason == "take-profit" and tv_reason == "stop-loss":
                categorized["PLATFORM_ZOOM_INTRABAR_TP"].append(trade_details)
            elif platform_reason == tv_reason:
                # Same exit reason but different price/time
                # This likely means both hit on same 1-min bar, tie-break applied
                categorized["ZOOM_1MIN_TIE_BREAK"].append(trade_details)
            else:
                # Different reasons but not the simple inversion cases
                # Could be tie-break or other edge case
                categorized["ZOOM_1MIN_TIE_BREAK"].append(trade_details)

        return categorized
