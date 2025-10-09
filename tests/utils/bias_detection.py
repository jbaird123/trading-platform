"""
Automated look-ahead bias detection for indicators.

This module provides tools to detect if an indicator uses future data
(look-ahead bias) by comparing vectorized computation (full dataset)
against bar-by-bar computation (historical data only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass
class BiasTestResult:
    """Result from bias detection test."""

    has_bias: bool
    max_difference: float
    biased_bars: list[pd.Timestamp]
    total_bars: int
    bars_tested: int

    @property
    def bias_percentage(self) -> float:
        """Percentage of bars with detected bias."""
        if self.bars_tested == 0:
            return 0.0
        return (len(self.biased_bars) / self.bars_tested) * 100.0

    def __str__(self) -> str:
        """Human-readable summary."""
        if not self.has_bias:
            return (
                f"✓ No bias detected "
                f"({self.bars_tested}/{self.total_bars} bars tested)"
            )
        return (
            f"✗ BIAS DETECTED!\n"
            f"  Max difference: {self.max_difference:.10f}\n"
            f"  Biased bars: {len(self.biased_bars)} "
            f"({self.bias_percentage:.1f}%)\n"
            f"  Total tested: {self.bars_tested}/{self.total_bars}"
        )


def detect_lookahead_bias(
    indicator_fn: Callable[[pd.DataFrame], pd.Series | pd.DataFrame],
    test_data: pd.DataFrame,
    tolerance: float = 1e-10,
    min_warmup: int = 50,
) -> BiasTestResult:
    """
    Detect look-ahead bias in an indicator by comparing vectorized vs
    bar-by-bar computation.

    Args:
        indicator_fn: Function that takes DataFrame and returns
                      Series/DataFrame. Must have signature:
                      fn(df: pd.DataFrame) -> pd.Series | pd.DataFrame
        test_data: Test dataset (must have OHLCV columns)
        tolerance: Maximum allowed difference (default: 1e-10)
        min_warmup: Minimum bars before starting comparison
                    (allows indicators to stabilize)

    Returns:
        BiasTestResult with detection details

    Example:
        >>> def my_indicator(df):
        ...     return df['close'].rolling(20).mean()
        >>> result = detect_lookahead_bias(my_indicator, test_data)
        >>> assert not result.has_bias
    """
    if len(test_data) < min_warmup:
        raise ValueError(
            f"Test data too short ({len(test_data)} bars). "
            f"Need at least {min_warmup} bars for warmup."
        )

    # Step 1: Vectorized computation (full dataset at once)
    signals_vectorized = indicator_fn(test_data.copy())

    # Convert to Series if DataFrame (take first column)
    if isinstance(signals_vectorized, pd.DataFrame):
        signals_vectorized = signals_vectorized.iloc[:, 0]

    # Step 2: Bar-by-bar computation (only historical data)
    signals_incremental = pd.Series(
        index=test_data.index, dtype=float, name="incremental"
    )

    for i in range(len(test_data)):
        # Only provide historical data up to current bar
        historical_only = test_data.iloc[: i + 1].copy()
        result = indicator_fn(historical_only)

        # Convert to Series if DataFrame
        if isinstance(result, pd.DataFrame):
            result = result.iloc[:, 0]

        # Take the last value (current bar's indicator value)
        signals_incremental.iloc[i] = result.iloc[-1]

    # Step 3: Compare results (skip warmup period)
    # Compare bars where EITHER method has non-NaN (to detect mismatches)
    after_warmup = signals_vectorized.index >= test_data.index[min_warmup]

    # Bars where both have values (normal comparison)
    both_valid = signals_vectorized.notna() & signals_incremental.notna() & after_warmup

    # Bars where NaN patterns differ (indicates bias)
    nan_mismatch = (
        signals_vectorized.notna() != signals_incremental.notna()
    ) & after_warmup

    if not both_valid.any() and not nan_mismatch.any():
        # No valid bars to compare
        return BiasTestResult(
            has_bias=False,
            max_difference=0.0,
            biased_bars=[],
            total_bars=len(test_data),
            bars_tested=0,
        )

    # Calculate absolute difference for valid bars
    diff = pd.Series(0.0, index=signals_vectorized.index)

    # For bars where both have values, compute difference
    if both_valid.any():
        diff[both_valid] = (
            signals_vectorized[both_valid] - signals_incremental[both_valid]
        ).abs()

    # For bars with NaN mismatch, mark as max difference
    # (different NaN patterns = bias)
    if nan_mismatch.any():
        diff[nan_mismatch] = float("inf")

    max_diff = diff[after_warmup].max()

    # Identify biased bars
    biased_mask = (diff > tolerance) & after_warmup
    biased_bars = diff[biased_mask].index.tolist()

    total_tested = int(both_valid.sum()) + int(nan_mismatch.sum())

    return BiasTestResult(
        has_bias=max_diff > tolerance,
        max_difference=float(max_diff) if max_diff != float("inf") else 1e100,
        biased_bars=biased_bars,
        total_bars=len(test_data),
        bars_tested=total_tested,
    )


def detect_lookahead_bias_multicolumn(
    indicator_fn: Callable[[pd.DataFrame], pd.DataFrame],
    test_data: pd.DataFrame,
    column_name: str,
    tolerance: float = 1e-10,
    min_warmup: int = 50,
) -> BiasTestResult:
    """
    Detect look-ahead bias for indicators that return DataFrames
    with multiple columns.

    Args:
        indicator_fn: Function returning DataFrame
        test_data: Test dataset
        column_name: Name of column to test
        tolerance: Maximum allowed difference
        min_warmup: Minimum bars before comparison

    Returns:
        BiasTestResult for specified column

    Example:
        >>> def swing_indicator(df):
        ...     return find_swing_points(df, 10, 10)
        >>> result = detect_lookahead_bias_multicolumn(
        ...     swing_indicator, test_data, 'swing_high'
        ... )
    """

    def _column_wrapper(df: pd.DataFrame) -> pd.Series:
        result_df = indicator_fn(df)
        if column_name not in result_df.columns:
            raise ValueError(
                f"Column '{column_name}' not in indicator output. "
                f"Available: {list(result_df.columns)}"
            )
        return result_df[column_name]

    return detect_lookahead_bias(_column_wrapper, test_data, tolerance, min_warmup)
