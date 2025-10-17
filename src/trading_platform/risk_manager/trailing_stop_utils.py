"""
1-Minute resolution exit processors.

This module provides the core logic for processing 1-minute bars chronologically
to determine trailing stop, fixed stop, and take-profit exits with precise timing.
"""

from __future__ import annotations

import pandas as pd

from .exit_utils import both_exits_in_same_bar


def process_1min_bars_for_fixed_stops(
    bars_1min: pd.DataFrame,
    side: str,
    stop_loss_level: float,
    take_profit_level: float | None,
    tie_break_policy: str,
) -> dict:
    """Process 1-minute bars for fixed stop-loss and take-profit exits.

    Args:
        bars_1min: DataFrame with 1-minute OHLC data
        side: Position side ("long" or "short")
        stop_loss_level: Fixed stop-loss price level
        take_profit_level: Fixed take-profit price level (or None)
        tie_break_policy: "stop_then_tp" or "tp_then_stop"

    Returns:
        dict with keys:
        - exit_occurred: bool
        - exit_bar_index: int (index where exit occurred) or None
        - exit_price: float (exit price) or None
        - exit_reason: str ("stop-loss" or "take-profit") or None
    """
    # Process each 1-minute bar chronologically
    for idx, bar in bars_1min.iterrows():
        # Check if stop was hit
        if side == "long":
            stop_hit = bar["low"] <= stop_loss_level
        else:
            stop_hit = bar["high"] >= stop_loss_level

        # Check if TP was hit
        tp_hit = False
        if take_profit_level is not None:
            if side == "long":
                tp_hit = bar["high"] >= take_profit_level
            else:
                tp_hit = bar["low"] <= take_profit_level

        # Determine exit
        if stop_hit and tp_hit:
            # Both hit on same bar - check if truly ambiguous
            if both_exits_in_same_bar(bar, stop_loss_level, take_profit_level):
                # Use tie-breaker policy
                if tie_break_policy == "stop_then_tp":
                    return {
                        "exit_occurred": True,
                        "exit_bar_index": idx,
                        "exit_price": stop_loss_level,
                        "exit_reason": "stop-loss",
                    }
                else:
                    return {
                        "exit_occurred": True,
                        "exit_bar_index": idx,
                        "exit_price": take_profit_level,
                        "exit_reason": "take-profit",
                    }
            else:
                # Can determine order from OHLC - conservatively assume stop first
                return {
                    "exit_occurred": True,
                    "exit_bar_index": idx,
                    "exit_price": stop_loss_level,
                    "exit_reason": "stop-loss",
                }
        elif stop_hit:
            return {
                "exit_occurred": True,
                "exit_bar_index": idx,
                "exit_price": stop_loss_level,
                "exit_reason": "stop-loss",
            }
        elif tp_hit:
            return {
                "exit_occurred": True,
                "exit_bar_index": idx,
                "exit_price": take_profit_level,
                "exit_reason": "take-profit",
            }

    # No exit occurred in any bar
    return {
        "exit_occurred": False,
        "exit_bar_index": None,
        "exit_price": None,
        "exit_reason": None,
    }


def process_1min_bars_for_trailing_stop(
    bars_1min: pd.DataFrame,
    entry_price: float,
    side: str,
    trailing_stop_offset: float,
    take_profit_price: float | None,
    tie_break_policy: str,
) -> dict:
    """Process 1-minute bars chronologically for trailing stop exit detection.

    Args:
        bars_1min: DataFrame with 1-minute OHLC bars
        entry_price: Entry price of the position
        side: "long" or "short"
        trailing_stop_offset: Trailing stop distance in canonical price units
            (e.g., 0.0020 for 20 pips on EUR/USD)
        take_profit_price: Take-profit price level, or None if no TP
        tie_break_policy: "stop_then_tp" or "tp_then_stop" for ambiguous bars

    Returns:
        Dictionary with:
            exit_occurred: bool - Whether an exit occurred
            exit_bar_index: int | None - Index of bar where exit occurred
            exit_price: float | None - Exact exit price (stop or TP level)
            exit_reason: str | None - "stop-loss" or "take-profit"

    Note:
        - Trailing stop is tracked after each bar based on peak/trough
        - Exit occurs AT the stop/TP level (not next bar open)
        - If both stop and TP hit on same bar, tie_break_policy is applied
    """
    # Initialize trailing stop tracking
    if side == "long":
        peak_or_trough = entry_price
        stop_level = entry_price - trailing_stop_offset
    else:  # short
        peak_or_trough = entry_price
        stop_level = entry_price + trailing_stop_offset

    # Process each 1-minute bar chronologically
    for idx, bar in bars_1min.iterrows():
        # Check if stop was hit on this bar (using CURRENT stop level)
        if side == "long":
            stop_hit = bar["low"] <= stop_level
        else:
            stop_hit = bar["high"] >= stop_level

        # Check if take-profit was hit on this bar
        tp_hit = False
        if take_profit_price is not None:
            if side == "long":
                tp_hit = bar["high"] >= take_profit_price
            else:
                tp_hit = bar["low"] <= take_profit_price

        # Determine exit based on what was hit
        if stop_hit and tp_hit:
            # Both hit - check if ambiguous on this 1min bar
            if both_exits_in_same_bar(bar, stop_level, take_profit_price):
                # Use tie-breaker policy
                if tie_break_policy == "stop_then_tp":
                    return {
                        "exit_occurred": True,
                        "exit_bar_index": idx,
                        "exit_price": stop_level,
                        "exit_reason": "stop-loss",
                    }
                else:  # tp_then_stop
                    return {
                        "exit_occurred": True,
                        "exit_bar_index": idx,
                        "exit_price": take_profit_price,
                        "exit_reason": "take-profit",
                    }
            else:
                # Not ambiguous on this bar - one hit before the other
                # Conservatively assume stop hit first
                return {
                    "exit_occurred": True,
                    "exit_bar_index": idx,
                    "exit_price": stop_level,
                    "exit_reason": "stop-loss",
                }
        elif stop_hit:
            # Only stop hit
            return {
                "exit_occurred": True,
                "exit_bar_index": idx,
                "exit_price": stop_level,
                "exit_reason": "stop-loss",
            }
        elif tp_hit:
            # Only TP hit
            return {
                "exit_occurred": True,
                "exit_bar_index": idx,
                "exit_price": take_profit_price,
                "exit_reason": "take-profit",
            }

        # No exit on this bar - update peak/trough and trailing stop for next bar
        if side == "long":
            # For long: track peak high, stop trails below it
            if bar["high"] > peak_or_trough:
                peak_or_trough = bar["high"]
                stop_level = peak_or_trough - trailing_stop_offset
        else:
            # For short: track trough low, stop trails above it
            if bar["low"] < peak_or_trough:
                peak_or_trough = bar["low"]
                stop_level = peak_or_trough + trailing_stop_offset

    # No exit occurred in any bar
    return {
        "exit_occurred": False,
        "exit_bar_index": None,
        "exit_price": None,
        "exit_reason": None,
    }
