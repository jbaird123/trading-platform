"""Generic analyzer for indicator-based stops (ATR, Bollinger, Keltner, etc.).

This analyzer handles ANY indicator-based stop loss mechanism. The specific
indicator calculation is provided via metadata.json configuration.

Supported indicator types:
- "atr": Average True Range based stops
- "bollinger": Bollinger Band based stops
- "keltner": Keltner Channel based stops
- Any future indicator can be added without code changes

Example metadata.json:
    {
        "exit_mechanisms": ["indicator_stop"],
        "indicator_stop_type": "atr",
        "indicator_stop_params": {"length": 14},
        "stop_distance_multiplier": 2.0
    }
"""

from typing import List, Optional

import pandas as pd

from tests.validation.ambiguity_analyzer import (
    AmbiguityAnalyzer,
    DiscrepancyResult,
)
from tests.validation.analyzers import register_analyzer


@register_analyzer("indicator_stop")
class IndicatorStopAnalyzer(AmbiguityAnalyzer):
    """Analyzes indicator-based stop exits (ATR, BB, KC, etc.).

    This is a GENERIC analyzer that works for any indicator-based stop.
    The specific indicator calculation is provided via metadata.
    """

    @classmethod
    def from_metadata(cls, metadata: dict):
        """Create analyzer from strategy metadata.

        Expected metadata fields:
        - "indicator_stop_type": "atr" | "bollinger" | "keltner" | etc.
        - "indicator_stop_params": {...}  # Indicator-specific params
        - "stop_distance_multiplier": 2.0  # How many indicator units away

        Args:
            metadata: Strategy metadata dictionary

        Returns:
            IndicatorStopAnalyzer instance

        Raises:
            ValueError: If required fields missing
        """
        indicator_type = metadata.get("indicator_stop_type")
        if not indicator_type:
            raise ValueError(
                "indicator_stop mechanism requires 'indicator_stop_type' in metadata"
            )

        params = metadata.get("indicator_stop_params", {})
        multiplier = metadata.get("stop_distance_multiplier", 1.0)

        return cls(
            indicator_type=indicator_type,
            indicator_params=params,
            multiplier=multiplier,
            tolerance=metadata.get("price_tolerance", 1e-5),
        )

    def __init__(
        self,
        indicator_type: str,
        indicator_params: dict,
        multiplier: float,
        tolerance: float,
    ):
        """Initialize indicator stop analyzer.

        Args:
            indicator_type: Type of indicator ("atr", "bollinger", etc.)
            indicator_params: Indicator calculation parameters
            multiplier: Distance multiplier (e.g., 2.0 for 2x ATR)
            tolerance: Price tolerance for matches
        """
        self.indicator_type = indicator_type
        self.indicator_params = indicator_params
        self.multiplier = multiplier
        self.tolerance = tolerance

        # Acceptable categories for indicator stops
        # Reuse the vetted category set used by trailing-stop validation.
        # Only these categories are treated as acceptable discrepancies.
        self.acceptable_categories = [
            "SAME_BAR_EXIT",
            "PLATFORM_ZOOM_INTRABAR_STOP",
            "PLATFORM_ZOOM_INTRABAR_TP",
        ]

    def analyze_discrepancy(
        self,
        platform_trade: pd.Series,
        tv_trade: pd.Series,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> DiscrepancyResult:
        """Analyze indicator-based stop discrepancy.

        Args:
            platform_trade: Platform trade Series
            tv_trade: TradingView trade Series
            ohlcv_data: Hourly OHLCV DataFrame with indicator columns
            ohlcv_1min: Optional 1-minute OHLCV for zoom verification
            **kwargs: Additional parameters

        Returns:
            DiscrepancyResult with category and explanation
        """
        # Extract indicator column name from OHLCV
        indicator_col = self._get_indicator_column(ohlcv_data)

        entry_time = pd.Timestamp(platform_trade["entry_time"])
        exit_time = pd.Timestamp(platform_trade["exit_time"])

        direction = platform_trade.get("side", "")
        exit_price = float(platform_trade["exit_price"])
        tv_price = float(tv_trade["exit_price"])
        metadata_base = {
            "direction": direction,
            "entry_time": str(entry_time),
            "entry_price": float(platform_trade["entry_price"]),
            "exit_time": str(exit_time),
            "platform_exit": exit_price,
            "platform_exit_reason": platform_trade.get("exit_reason", ""),
            "tv_exit": tv_price,
            "tv_exit_reason": tv_trade.get("exit_reason", ""),
            "price_diff_pips": abs(exit_price - tv_price) * 10000,
        }

        prev_rows = ohlcv_data.loc[:exit_time]
        expected_stop_prev = None
        if len(prev_rows) >= 2:
            prev_bar_series = prev_rows.iloc[-2]
            prev_close = float(prev_bar_series["close"])
            prev_indicator_value = float(prev_bar_series[indicator_col])
            if direction == "long":
                expected_stop_prev = prev_close - prev_indicator_value * self.multiplier
            else:
                expected_stop_prev = prev_close + prev_indicator_value * self.multiplier

        # Category 1: Same bar entry/exit
        if entry_time == exit_time:
            return DiscrepancyResult(
                category="SAME_BAR_EXIT",
                explanation=(
                    "Entry and exit on same bar. TradingView historical backtesting "
                    "cannot detect intra-bar stop hits on entry bar."
                ),
                metadata=dict(metadata_base),
                is_acceptable=True,
                confidence=1.0,
            )

        # Category 2: Indicator recalculation
        # Check if indicator value changed significantly between entry and exit
        entry_indicator = float(ohlcv_data.loc[entry_time, indicator_col])  # type: ignore[arg-type]
        exit_indicator = float(ohlcv_data.loc[exit_time, indicator_col])  # type: ignore[arg-type]

        indicator_change_pct = abs(exit_indicator - entry_indicator) / entry_indicator

        if indicator_change_pct > 0.1:  # 10% change threshold
            if (
                expected_stop_prev is not None
                and abs(exit_price - expected_stop_prev) <= self.tolerance * 5
                and abs(tv_price - expected_stop_prev) > self.tolerance
            ):
                metadata = dict(metadata_base)
                metadata["expected_stop"] = expected_stop_prev
                return DiscrepancyResult(
                    category="PLATFORM_ZOOM_INTRABAR_STOP",
                    explanation=(
                        "Platform exit matches the prior bar ATR stop while "
                        "TradingView exited at a different price. This "
                        "indicates TradingView missed the intra-bar stop hit."
                    ),
                    metadata=metadata,
                    is_acceptable=True,
                    confidence=0.8,
                )

            metadata = dict(metadata_base)
            metadata.update(
                {
                    "entry_indicator_value": entry_indicator,
                    "exit_indicator_value": exit_indicator,
                    "indicator_change_pct": indicator_change_pct,
                }
            )
            return DiscrepancyResult(
                category="UNEXPLAINED",
                explanation=(
                    f"{self.indicator_type.upper()} changed from "
                    f"{entry_indicator:.5f} (entry) to {exit_indicator:.5f} (exit), "
                    f"a {indicator_change_pct:.1%} change. "
                    "This difference is currently not an approved exception and "
                    "requires manual review."
                ),
                metadata=metadata,
                is_acceptable=False,
                confidence=0.5,
            )

        # Category 3: Entry bar indicator difference
        # Check if indicator differs on entry bar between platforms
        # (This is analogous to entry bar MFE for trailing stops)
        entry_bar_indicator = float(ohlcv_data.loc[entry_time, indicator_col])  # type: ignore[arg-type]

        # Get next bar indicator (when stop would first be calculated)
        next_bars = ohlcv_data.loc[entry_time:exit_time].iloc[1:]
        if len(next_bars) > 0:
            next_bar_indicator = float(next_bars.iloc[0][indicator_col])

            indicator_diff = abs(next_bar_indicator - entry_bar_indicator)
            if indicator_diff > self.tolerance:
                metadata = dict(metadata_base)
                metadata.update(
                    {
                        "entry_bar_indicator": entry_bar_indicator,
                        "next_bar_indicator": next_bar_indicator,
                        "indicator_diff": indicator_diff,
                    }
                )
                if (
                    expected_stop_prev is not None
                    and abs(exit_price - expected_stop_prev) <= self.tolerance * 5
                    and abs(tv_price - expected_stop_prev) > self.tolerance
                ):
                    metadata = dict(metadata_base)
                    metadata["expected_stop"] = expected_stop_prev
                    return DiscrepancyResult(
                        category="PLATFORM_ZOOM_INTRABAR_STOP",
                        explanation=(
                            "Platform exit aligned with the prior bar ATR stop "
                            "while TradingView used a different price. "
                            "TradingView likely missed the intra-bar stop hit."
                        ),
                        metadata=metadata,
                        is_acceptable=True,
                        confidence=0.8,
                    )

                return DiscrepancyResult(
                    category="UNEXPLAINED",
                    explanation=(
                        f"{self.indicator_type.upper()} on entry bar "
                        f"({entry_bar_indicator:.5f}) differs from next bar "
                        f"({next_bar_indicator:.5f}). "
                        "Entry-bar indicator differences are not an approved "
                        "exception for indicator-based stops and need review."
                    ),
                    metadata=metadata,
                    is_acceptable=False,
                    confidence=0.5,
                )

        # Category 4: Platform zoom detected intrabar stop
        if ohlcv_1min is not None:
            zoom_result = self._check_indicator_stop_zoom(
                platform_trade, tv_trade, ohlcv_data, ohlcv_1min, indicator_col
            )
            if zoom_result:
                return zoom_result

        # Unexplained
        if (
            expected_stop_prev is not None
            and abs(exit_price - expected_stop_prev) <= self.tolerance * 5
            and abs(tv_price - expected_stop_prev) > self.tolerance
        ):
            metadata_zoom = dict(metadata_base)
            metadata_zoom["expected_stop"] = expected_stop_prev
            return DiscrepancyResult(
                category="PLATFORM_ZOOM_INTRABAR_STOP",
                explanation=(
                    "Platform exit matches the calculated prior bar ATR stop "
                    "but TradingView exited elsewhere. This is a known "
                    "TradingView limitation with intra-bar stop handling."
                ),
                metadata=metadata_zoom,
                is_acceptable=True,
                confidence=0.8,
            )

        metadata = dict(metadata_base)
        metadata.update(
            {
                "indicator_type": self.indicator_type,
            }
        )
        return DiscrepancyResult(
            category="UNEXPLAINED",
            explanation=(
                f"Unable to categorize {self.indicator_type} stop discrepancy. "
                f"Platform exit: {platform_trade['exit_price']:.5f} @ "
                f"{exit_time}, "
                f"TradingView exit: {tv_trade['exit_price']:.5f} @ "
                f"{tv_trade['exit_time']}"
            ),
            metadata=metadata,
            is_acceptable=False,
            confidence=0.0,
        )

    def _get_indicator_column(self, ohlcv_data: pd.DataFrame) -> str:
        """Find the indicator column in OHLCV data.

        For ATR with length=14, could be: "ATR", "atr", "ATR_14", "atr_14"

        Args:
            ohlcv_data: OHLCV DataFrame with indicator columns

        Returns:
            Column name for the indicator

        Raises:
            ValueError: If indicator column not found
        """
        # Try common naming patterns
        length = self.indicator_params.get("length", "")
        possible_names = [
            self.indicator_type.upper(),
            self.indicator_type.lower(),
            f"{self.indicator_type.upper()}_{length}",
            f"{self.indicator_type.lower()}_{length}",
            f"{self.indicator_type.upper()}{length}",
            f"{self.indicator_type.lower()}{length}",
        ]

        for name in possible_names:
            if name in ohlcv_data.columns:
                return name

        raise ValueError(
            f"Could not find {self.indicator_type} indicator column in OHLCV data. "
            f"Tried: {possible_names}. "
            f"Available: {list(ohlcv_data.columns)}"
        )

    def _check_indicator_stop_zoom(
        self,
        platform_trade: pd.Series,
        tv_trade: pd.Series,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: pd.DataFrame,
        indicator_col: str,
    ) -> Optional[DiscrepancyResult]:
        """Check if discrepancy is due to platform's 1-minute zoom feature.

        Uses 1-minute data to verify platform's exit matches exact indicator
        stop hit when using intra-bar resolution.

        Args:
            platform_trade: Platform trade Series
            tv_trade: TradingView trade Series
            ohlcv_data: Hourly OHLCV data
            ohlcv_1min: 1-minute OHLCV data
            indicator_col: Name of indicator column

        Returns:
            DiscrepancyResult if zoom discrepancy detected, None otherwise
        """
        # TODO: Implement 1-minute zoom verification for indicator stops
        # This would require:
        # 1. Simulate indicator stop using 1-minute data
        # 2. Verify platform exit matches simulated stop hit
        # 3. Explain timing difference vs TradingView

        # For now, return None (not implemented)
        # This can be added later if needed for specific indicator types
        return None

    def get_acceptable_categories(self) -> List[str]:
        """Get list of acceptable discrepancy categories."""
        return self.acceptable_categories

    def get_analyzer_type(self) -> str:
        """Get analyzer type name for logging."""
        return f"IndicatorStop[{self.indicator_type}]"
