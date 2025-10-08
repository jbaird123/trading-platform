"""
Tests for custom indicator functions.
"""

import pandas as pd
from trading_platform.strategy.custom_indicators import find_swing_points


def test_find_swing_points():
    """Test the find_swing_points function with a clear swing high and low."""
    # Create a sample DataFrame with a clear swing high and low
    data = {
        "high": [10, 20, 30, 40, 30, 20, 10, 20, 30, 25, 15],
        "low": [5, 15, 25, 35, 25, 15, 5, 15, 20, 20, 10],
        "close": [7, 17, 27, 37, 27, 17, 7, 17, 27, 22, 12],
        "open": [6, 16, 26, 36, 26, 16, 6, 16, 26, 23, 13],
    }
    candles = pd.DataFrame(data)

    # Find swing points
    swings = find_swing_points(candles, left_bars=3, right_bars=3)

    # Expected results
    expected_high_index = 3
    expected_high_value = 40
    expected_low_index = 6
    expected_low_value = 5

    # Check swing high
    assert swings["swing_high"].iloc[expected_high_index] == expected_high_value
    assert swings["swing_high"].dropna().shape[0] == 1

    # Check swing low
    assert swings["swing_low"].iloc[expected_low_index] == expected_low_value
    assert swings["swing_low"].dropna().shape[0] == 1

    # Check that other values are NaN
    assert swings["swing_high"].drop(index=expected_high_index).isna().all()
    assert swings["swing_low"].drop(index=expected_low_index).isna().all()


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

    # Check that no swing points were found
    assert swings["swing_high"].dropna().empty
    assert swings["swing_low"].dropna().empty


def test_find_swing_points_multiple_swings():
    """Test find_swing_points on data with multiple swings."""
    data = {
        "high": [10, 30, 20, 40, 30, 50, 40, 20, 10],
        "low": [5, 25, 10, 35, 20, 45, 30, 15, 5],
        "close": [7, 27, 15, 37, 25, 47, 35, 17, 7],
        "open": [6, 26, 12, 36, 22, 46, 32, 16, 6],
    }
    candles = pd.DataFrame(data)

    swings = find_swing_points(candles, left_bars=1, right_bars=1)

    # Expected swing highs
    assert swings["swing_high"].iloc[1] == 30
    assert swings["swing_high"].iloc[3] == 40
    assert swings["swing_high"].iloc[5] == 50
    assert swings["swing_high"].dropna().shape[0] == 3

    # Expected swing lows
    assert swings["swing_low"].iloc[2] == 10
    assert swings["swing_low"].iloc[4] == 20
    assert swings["swing_low"].dropna().shape[0] == 2
