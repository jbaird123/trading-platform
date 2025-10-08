"""
Tests for custom indicator functions.
"""

import pandas as pd
from trading_platform.strategy.custom_indicators import find_swing_points


def test_find_swing_points():
    """Test the find_swing_points function with a clear swing high and low.

    Note: Signals are lagged by right_bars periods to avoid look-ahead bias.
    If bar 3 is a swing high with right_bars=3, the signal appears at bar 6.
    """
    # Create a sample DataFrame with a clear swing high and low
    data = {
        "high": [10, 20, 30, 40, 30, 20, 10, 20, 30, 25, 15],
        "low": [5, 15, 25, 35, 25, 15, 5, 15, 20, 20, 10],
        "close": [7, 17, 27, 37, 27, 17, 7, 17, 27, 22, 12],
        "open": [6, 16, 26, 36, 26, 16, 6, 16, 26, 23, 13],
    }
    candles = pd.DataFrame(data)

    # Find swing points with left_bars=3, right_bars=3
    swings = find_swing_points(candles, left_bars=3, right_bars=3)

    # Bar 3 (high=40) is the swing high, but signal appears at bar 3+3=6
    # Bar 6 (low=5) is the swing low, but signal would appear at bar 6+3=9
    # However, we need at least 3 bars after bar 6, so check if bar 9 exists

    # Check swing high signal (bar 3 detected, signal at bar 6)
    assert swings["swing_high"].iloc[6] == 1.0
    assert (swings["swing_high"] == 1.0).sum() == 1

    # Check swing low signal (bar 6 detected, signal at bar 9)
    assert swings["swing_low"].iloc[9] == 1.0
    assert (swings["swing_low"] == 1.0).sum() == 1

    # Check that other values are 0.0
    assert (swings["swing_high"].drop(index=6) == 0.0).all()
    assert (swings["swing_low"].drop(index=9) == 0.0).all()


def test_find_swing_points_no_swings():
    """Test find_swing_points on data with no clear swings."""
    # Create a sample DataFrame with a steady uptrend (no peaks/troughs)
    data = {
        "high": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "low": [5, 15, 25, 35, 45, 55, 65, 75, 85, 95],
        "close": [7, 17, 27, 37, 47, 57, 67, 77, 87, 97],
        "open": [6, 16, 26, 36, 46, 56, 66, 76, 86, 96],
    }
    candles = pd.DataFrame(data)

    # Find swing points
    swings = find_swing_points(candles, left_bars=3, right_bars=3)

    # Check that no swing points were found (all values should be 0.0)
    assert (swings["swing_high"] == 0.0).all()
    assert (swings["swing_low"] == 0.0).all()


def test_find_swing_points_multiple_swings():
    """Test find_swing_points on data with multiple swings.

    With left_bars=1, right_bars=1:
    - Bar 1 (high=30) is a swing high, signal at bar 1+1=2
    - Bar 2 (low=10) is a swing low, signal at bar 2+1=3
    - Bar 3 (high=40) is a swing high, signal at bar 3+1=4
    - Bar 4 (low=20) is a swing low, signal at bar 4+1=5
    - Bar 5 (high=50) is a swing high, signal at bar 5+1=6
    """
    data = {
        "high": [10, 30, 20, 40, 30, 50, 40, 20, 10],
        "low": [5, 25, 10, 35, 20, 45, 30, 15, 5],
        "close": [7, 27, 15, 37, 25, 47, 35, 17, 7],
        "open": [6, 26, 12, 36, 22, 46, 32, 16, 6],
    }
    candles = pd.DataFrame(data)

    swings = find_swing_points(candles, left_bars=1, right_bars=1)

    # Expected swing highs (signals appear 1 bar after the actual swing)
    assert swings["swing_high"].iloc[2] == 1.0  # Bar 1 detected, signal at bar 2
    assert swings["swing_high"].iloc[4] == 1.0  # Bar 3 detected, signal at bar 4
    assert swings["swing_high"].iloc[6] == 1.0  # Bar 5 detected, signal at bar 6
    assert (swings["swing_high"] == 1.0).sum() == 3

    # Expected swing lows (signals appear 1 bar after the actual swing)
    assert swings["swing_low"].iloc[3] == 1.0  # Bar 2 detected, signal at bar 3
    assert swings["swing_low"].iloc[5] == 1.0  # Bar 4 detected, signal at bar 5
    assert (swings["swing_low"] == 1.0).sum() == 2
