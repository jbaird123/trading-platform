"""
Custom indicator functions that are not available in pandas-ta.
"""

import pandas as pd


def find_swing_points(
    candles: pd.DataFrame,
    left_bars: int = 10,
    right_bars: int = 10,
    high_col: str = "high",
    low_col: str = "low",
) -> pd.DataFrame:
    """
    Identifies swing points (highs and lows) in the price data.
    A swing high is a candle with a high that is the highest in a window of
    `left_bars` to the left and `right_bars` to the right.
    A swing low is a candle with a low that is the lowest in a window of
    `left_bars` to the left and `right_bars` to the right.
    Args:
        candles (pd.DataFrame): DataFrame with candlestick data.
        left_bars (int): Number of bars to the left to consider for a swing.
        right_bars (int): Number of bars to the right to consider for a swing.
        high_col (str): Name of the high price column.
        low_col (str): Name of the low price column.
    Returns:
        pd.DataFrame: A DataFrame with 'swing_high' and 'swing_low' columns,
                      containing the price of the swing point at the candle
                      where it occurred and NaN otherwise.
    """
    window_size = left_bars + right_bars + 1

    # Find rolling max/min in a centered window
    # The min_periods argument ensures we have a full window
    rolling_max = (
        candles[high_col]
        .rolling(window=window_size, center=True, min_periods=window_size)
        .max()
    )
    rolling_min = (
        candles[low_col]
        .rolling(window=window_size, center=True, min_periods=window_size)
        .min()
    )

    # Identify swing high/low candidates
    swing_high_mask = candles[high_col] == rolling_max
    swing_low_mask = candles[low_col] == rolling_min

    # Filter for the first occurrence in a sequence of consecutive identical highs/lows
    unique_swing_high_mask = swing_high_mask & ~swing_high_mask.shift(1).fillna(False)
    unique_swing_low_mask = swing_low_mask & ~swing_low_mask.shift(1).fillna(False)

    # Create the output DataFrame
    swings = pd.DataFrame(index=candles.index)
    swings["swing_high"] = candles[high_col][unique_swing_high_mask]
    swings["swing_low"] = candles[low_col][unique_swing_low_mask]

    return swings
