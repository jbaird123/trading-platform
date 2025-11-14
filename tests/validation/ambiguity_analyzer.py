#!/usr/bin/env python3
"""Pluggable Ambiguity Analyzer Framework

This module provides the base architecture for detecting and categorizing
all types of exit ambiguities between platform and TradingView backtests.

ARCHITECTURE:
=============
The framework uses a pluggable analyzer pattern where different ambiguity
types are handled by specialized analyzers that all implement the same interface.

Current ambiguity types supported:
1. Trailing stop ambiguities (entry bar MFE, intrabar zoom, same bar exit)
2. Fixed stop + TP ambiguities (same bar hit, tie-break policy differences)
3. Signal-based stop ambiguities (ATR recalculation, signal changes) - FUTURE

Each analyzer type can be used standalone OR composed together for strategies
that combine multiple exit mechanisms (e.g., trailing stop + fixed TP).

DESIGN PRINCIPLES:
==================
1. Single Responsibility: Each analyzer handles ONE type of ambiguity
2. Composability: Analyzers can be chained/combined for complex strategies
3. Extensibility: New ambiguity types added by creating new analyzer classes
4. Consistency: All analyzers return same format (category, explanation, metadata)
5. Testability: Each analyzer can be tested in isolation

USAGE EXAMPLE:
==============
    # Single analyzer for trailing stop only strategy
    from tests.validation.trailing_stop_analyzer import TrailingStopAmbiguityAnalyzer

    analyzer = TrailingStopAmbiguityAnalyzer(
        trailing_stop_pips=0.0020,
        take_profit_pips=None,
    )

    result = analyzer.analyze_discrepancy(
        platform_trade, tv_trade, ohlcv_data, ohlcv_1min
    )

    # Composite analyzer for trailing stop + fixed TP strategy
    from tests.validation.ambiguity_analyzer import CompositeAmbiguityAnalyzer
    from tests.validation.fixed_stop_tp_analyzer import FixedStopTPAmbiguityAnalyzer

    composite = CompositeAmbiguityAnalyzer([
        TrailingStopAmbiguityAnalyzer(...),
        FixedStopTPAmbiguityAnalyzer(...),
    ])

    result = composite.analyze_discrepancy(...)

For detailed design rationale, see: docs/testing/ambiguity_analyzer_framework.md
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class DiscrepancyResult:
    """Result from analyzing a single trade discrepancy.

    Attributes:
        category: Category name (e.g., "SAME_BAR_EXIT", "UNEXPLAINED")
        explanation: Human-readable explanation of the discrepancy
        metadata: Additional data for verification (MFE values, zoom times, etc.)
        is_acceptable: True if this is a known/acceptable discrepancy
        confidence: Confidence level (1.0 = verified, 0.5 = inferred, 0.0 = unknown)

    Example:
        >>> result = DiscrepancyResult(
        ...     category="TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
        ...     explanation="Platform adjusted stop for entry bar MFE...",
        ...     metadata={"entry_bar_mfe_pips": 11.0, "mfe_diff_pips": 9.4},
        ...     is_acceptable=True,
        ...     confidence=1.0
        ... )
    """

    category: str
    explanation: str
    metadata: Dict[str, Any]
    is_acceptable: bool
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization."""
        return {
            "category": self.category,
            "explanation": self.explanation,
            "metadata": self.metadata,
            "is_acceptable": self.is_acceptable,
            "confidence": self.confidence,
        }


class AmbiguityAnalyzer(ABC):
    """Base class for all ambiguity analyzers.

    Each analyzer implementation handles a specific type of exit ambiguity
    (trailing stops, fixed stops, signal-based stops, etc.).

    Subclasses must implement:
    - analyze_discrepancy(): Analyze single trade discrepancy
    - get_acceptable_categories(): Return list of known acceptable categories
    - get_analyzer_type(): Return analyzer type name for logging
    """

    @abstractmethod
    def analyze_discrepancy(
        self,
        platform_trade: pd.Series,
        tv_trade: pd.Series,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> DiscrepancyResult:
        """Analyze a single trade discrepancy.

        Args:
            platform_trade: Platform trade as pandas Series with fields:
                entry_time, exit_time, entry_price, exit_price, side, exit_reason
            tv_trade: TradingView trade as pandas Series (same format)
            ohlcv_data: Hourly OHLCV DataFrame (indexed by timestamp)
            ohlcv_1min: Optional 1-minute OHLCV for zoom verification
            **kwargs: Additional analyzer-specific parameters

        Returns:
            DiscrepancyResult with category, explanation, and metadata

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        pass

    @abstractmethod
    def get_acceptable_categories(self) -> List[str]:
        """Get list of category names considered acceptable by this analyzer.

        Returns:
            List of category name strings (e.g., ["SAME_BAR_EXIT", ...])

        Example:
            >>> analyzer = TrailingStopAmbiguityAnalyzer(...)
            >>> analyzer.get_acceptable_categories()
            ['SAME_BAR_EXIT', 'TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT', ...]
        """
        pass

    @abstractmethod
    def get_analyzer_type(self) -> str:
        """Get analyzer type name for logging/debugging.

        Returns:
            Analyzer type string (e.g., "TrailingStop", "FixedStopTP")
        """
        pass

    def analyze_discrepancies(
        self,
        platform_df: pd.DataFrame,
        tv_df: pd.DataFrame,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze all discrepancies and group by category.

        This is the standard batch analysis method that processes multiple
        trades and groups results by category name. Most analyzers can use
        the default implementation.

        Args:
            platform_df: DataFrame of platform trades
            tv_df: DataFrame of TradingView trades (aligned with platform_df)
            ohlcv_data: Hourly OHLCV data
            ohlcv_1min: Optional 1-minute OHLCV data
            **kwargs: Additional analyzer-specific parameters

        Returns:
            Dictionary mapping category names to lists of trade dicts:
            {
                "SAME_BAR_EXIT": [
                    {"trade_num": 1, "explanation": "...", ...},
                    ...
                ],
                "UNEXPLAINED": [...],
                ...
            }
        """
        # Initialize result dictionary with all possible categories
        categories: dict[str, list[Dict[str, Any]]] = {
            cat: []
            for cat in self.get_acceptable_categories()  # noqa: E501
        }
        categories["UNEXPLAINED"] = []

        # Analyze each trade pair
        for i in range(len(platform_df)):
            platform_trade = platform_df.iloc[i]
            tv_trade = tv_df.iloc[i]
            trade_num = i + 1

            # Only analyze if there's a discrepancy
            if not self._has_discrepancy(platform_trade, tv_trade):
                continue

            # Analyze the discrepancy
            result = self.analyze_discrepancy(
                platform_trade,
                tv_trade,
                ohlcv_data,
                ohlcv_1min,
                **kwargs,
            )

            # Add to appropriate category
            trade_dict = {
                "trade_num": trade_num,
                "trade_index": i,
                "direction": str(platform_trade.get("side", "")),
                "entry_time": str(platform_trade.get("entry_time")),
                "entry_price": float(platform_trade.get("entry_price", 0.0)),
                "exit_time": str(platform_trade.get("exit_time")),
                "platform_exit": float(platform_trade.get("exit_price", 0.0)),
                "platform_exit_reason": platform_trade.get("exit_reason", ""),
                "tv_exit": float(tv_trade.get("exit_price", 0.0)),
                "tv_exit_reason": tv_trade.get("exit_reason", ""),
                "price_diff_pips": abs(
                    float(platform_trade.get("exit_price", 0.0))
                    - float(tv_trade.get("exit_price", 0.0))
                )
                * 10000,
                "explanation": result.explanation,
                **result.metadata,
            }

            if result.category in categories:
                categories[result.category].append(trade_dict)
            else:
                # Unknown category - treat as unexplained
                categories["UNEXPLAINED"].append(trade_dict)

        return categories

    def _has_discrepancy(
        self,
        platform_trade: pd.Series,
        tv_trade: pd.Series,
        tolerance: float = 0.00001,
    ) -> bool:
        """Check if two trades have a discrepancy.

        Default implementation checks exit price difference.
        Subclasses can override for custom discrepancy detection.

        Args:
            platform_trade: Platform trade Series
            tv_trade: TradingView trade Series
            tolerance: Price tolerance for considering prices equal

        Returns:
            True if trades have a discrepancy
        """
        price_diff = float(abs(platform_trade["exit_price"] - tv_trade["exit_price"]))
        return bool(price_diff > tolerance)

    @property
    def KNOWN_ACCEPTABLE_CATEGORIES(self) -> List[str]:
        """Convenience property for accessing acceptable categories.

        This provides compatibility with existing code that uses
        KNOWN_ACCEPTABLE_CATEGORIES as an attribute.

        Returns:
            List of acceptable category names
        """
        return self.get_acceptable_categories()

    def generate_summary_report(
        self, categories: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """Generate a human-readable summary report of discrepancies.

        Args:
            categories: Dictionary of categorized discrepancies from
                analyze_discrepancies()

        Returns:
            Formatted string report showing breakdown of discrepancies

        Example output:
            ========================================
            VALIDATION - DISCREPANCY ANALYSIS
            ========================================

            Total discrepancies: 15
            Explained (acceptable): 15
            Unexplained (requires investigation): 0

            ✓ PASS: All 15 discrepancies are explained and acceptable

            Breakdown:
              - SAME_BAR_EXIT: 8
              - PLATFORM_ZOOM_INTRABAR_STOP: 7
            ========================================
        """
        analyzer_type = self.get_analyzer_type()
        total_discrepancies = sum(len(v) for v in categories.values())
        total_explained = sum(
            len(categories[cat]) for cat in self.get_acceptable_categories()
        )
        total_unexplained = len(categories.get("UNEXPLAINED", []))

        report = []
        report.append("=" * 100)
        report.append(f"{analyzer_type.upper()} VALIDATION - " f"DISCREPANCY ANALYSIS")
        report.append("=" * 100)
        report.append(f"\nTotal discrepancies: {total_discrepancies}")
        report.append(f"Explained (acceptable): {total_explained}")
        report.append(f"Unexplained (requires investigation): " f"{total_unexplained}")

        if total_unexplained == 0:
            report.append(
                f"\n✓ PASS: All {total_discrepancies} discrepancies "
                f"are explained and acceptable"
            )
            report.append("\nBreakdown:")
            for cat in self.get_acceptable_categories():
                count = len(categories.get(cat, []))
                if count > 0:
                    report.append(f"  - {cat}: {count}")
        else:
            report.append(
                f"\n✗ FAIL: {total_unexplained} unexplained " f"discrepancies"
            )
            report.append("\nUnexplained trades:")
            for trade in categories.get("UNEXPLAINED", []):
                trade_num = trade.get("trade_num", "?")
                direction = trade.get("direction", "?")
                price_diff = trade.get("price_diff_pips", 0.0)
                report.append(
                    f"  - Trade #{trade_num}: {direction} "
                    f"({price_diff:.1f} pips difference)"
                )

        report.append("=" * 100)
        return "\n".join(report)

    def assert_all_explained(self, categories: Dict[str, List[Dict[str, Any]]]) -> None:
        """Assert that all discrepancies are explained.

        Args:
            categories: Dictionary of categorized discrepancies

        Raises:
            AssertionError: If there are unexplained discrepancies
        """
        unexplained = categories.get("UNEXPLAINED", [])
        if len(unexplained) > 0:
            unexplained_trades = [t["trade_num"] for t in unexplained]
            analyzer_type = self.get_analyzer_type()
            raise AssertionError(
                f"Found {len(unexplained)} unexplained {analyzer_type} "
                f"discrepancies. "
                f"All discrepancies must be categorized as acceptable. "
                f"Unexplained trades: {unexplained_trades}. "
                f"This may indicate a bug in the platform or a new "
                f"TradingView behavior."
            )


class CompositeAmbiguityAnalyzer(AmbiguityAnalyzer):
    """Composite analyzer that chains multiple analyzers.

    This allows handling strategies with multiple exit mechanisms
    (e.g., trailing stop + fixed TP) by trying each analyzer in sequence.

    The first analyzer that returns an acceptable category wins.
    If no analyzer explains the discrepancy, it's marked as UNEXPLAINED.

    Example:
        >>> composite = CompositeAmbiguityAnalyzer([
        ...     TrailingStopAmbiguityAnalyzer(...),
        ...     FixedStopTPAmbiguityAnalyzer(...),
        ... ])
        >>> result = composite.analyze_discrepancy(...)
    """

    def __init__(self, analyzers: List[AmbiguityAnalyzer]):
        """Initialize composite with list of analyzers.

        Args:
            analyzers: List of analyzer instances to try in order

        Raises:
            ValueError: If analyzers list is empty
        """
        if not analyzers:
            raise ValueError("CompositeAnalyzer requires at least one analyzer")
        self.analyzers = analyzers

    def analyze_discrepancy(
        self,
        platform_trade: pd.Series,
        tv_trade: pd.Series,
        ohlcv_data: pd.DataFrame,
        ohlcv_1min: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> DiscrepancyResult:
        """Try each analyzer in sequence until one explains the discrepancy.

        Returns:
            DiscrepancyResult from first analyzer that finds acceptable category,
            or UNEXPLAINED if none match
        """
        for analyzer in self.analyzers:
            result = analyzer.analyze_discrepancy(
                platform_trade,
                tv_trade,
                ohlcv_data,
                ohlcv_1min,
                **kwargs,
            )

            # If this analyzer found an acceptable category, return it
            if result.is_acceptable:
                return result

        # No analyzer explained it
        return DiscrepancyResult(
            category="UNEXPLAINED",
            explanation="No analyzer could explain this discrepancy",
            metadata={},
            is_acceptable=False,
            confidence=0.0,
        )

    def get_acceptable_categories(self) -> List[str]:
        """Combine acceptable categories from all analyzers."""
        categories = set()
        for analyzer in self.analyzers:
            categories.update(analyzer.get_acceptable_categories())
        return sorted(list(categories))

    def get_analyzer_type(self) -> str:
        """Return composite type with sub-analyzers listed."""
        sub_types = [a.get_analyzer_type() for a in self.analyzers]
        return f"Composite[{', '.join(sub_types)}]"
