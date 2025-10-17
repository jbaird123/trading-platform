"""
Exit ambiguity detection utilities.

This module provides functions for detecting when OHLC bar data is ambiguous
and requires 1-minute resolution to determine the correct exit behavior.
"""

from __future__ import annotations

import pandas as pd


def is_trailing_stop_ambiguous(bar: pd.Series, trailing_stop_level: float) -> bool:
    """Check if trailing stop exit is ambiguous on primary timeframe.

    Ambiguity exists when the trailing stop level is within the bar's range,
    because we cannot determine from OHLC alone whether the stop was hit
    due to the intra-bar order of price movements being unknown.

    Args:
        bar: OHLC bar data with 'low' and 'high' fields
        trailing_stop_level: The trailing stop price level

    Returns:
        True if ambiguous (stop level is between bar's low and high),
        False otherwise

    Note:
        This function does NOT consider take-profit level. It only determines
        if we need to zoom to 1-minute resolution for trailing stop processing.
    """
    # Ambiguous if trailing stop is between bar's high and low
    # This is the fundamental problem: we don't know the intra-bar order of movements
    return bar["low"] <= trailing_stop_level <= bar["high"]


def both_exits_in_same_bar(
    bar: pd.Series, stop_loss_level: float, take_profit_level: float
) -> bool:
    """Check if both stop-loss and take-profit are in the same bar's range.

    This function is used at 1-minute resolution as a tie-breaker to determine
    when we need to apply a tie-breaking policy because both exits were reached
    on the same 1-minute bar.

    Args:
        bar: OHLC bar data with 'low' and 'high' fields
        stop_loss_level: The stop-loss price level
        take_profit_level: The take-profit price level

    Returns:
        True if both stop and TP are within the bar's range (requires tie-breaking),
        False otherwise
    """
    stop_in_range = bar["low"] <= stop_loss_level <= bar["high"]
    tp_in_range = bar["low"] <= take_profit_level <= bar["high"]
    return stop_in_range and tp_in_range
