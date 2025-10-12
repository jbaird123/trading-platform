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
    Identifies swing points (highs and lows) in the price data WITHOUT look-ahead bias.

    A swing high at bar N is detected when:
    - Bar N's high is the highest in window [N-left_bars, N+right_bars]
    - The signal is emitted at bar N+right_bars (after confirmation)

    A swing low at bar N is detected when:
    - Bar N's low is the lowest in window [N-left_bars, N+right_bars]
    - The signal is emitted at bar N+right_bars (after confirmation)

    This implementation avoids look-ahead bias by only using historical data.
    The signal naturally lags by `right_bars` periods because we must wait
    for confirmation that no higher high (or lower low) occurred.

    Args:
        candles (pd.DataFrame): DataFrame with candlestick data.
        left_bars (int): Number of bars to the left to consider for a swing.
        right_bars (int): Number of bars to the right to consider for a swing.
        high_col (str): Name of the high price column.
        low_col (str): Name of the low price column.
    Returns:
        pd.DataFrame: A DataFrame with 'swing_high' and 'swing_low' columns,
                      containing 1.0 when a swing point is confirmed, 0.0 otherwise.
                      The signal appears at bar N+right_bars when bar N is identified
                      as a swing point.
    """
    n = len(candles)
    swing_high = pd.Series(0.0, index=candles.index)
    swing_low = pd.Series(0.0, index=candles.index)

    # For each bar, check if it's a swing point
    # We can only check bars where we have sufficient history on both sides
    for i in range(left_bars, n - right_bars):
        # Get the window around bar i
        window_start = i - left_bars
        window_end = i + right_bars + 1  # +1 for exclusive slice end

        # Check if bar i is a swing high
        window_highs = candles[high_col].iloc[window_start:window_end]
        if candles[high_col].iloc[i] == window_highs.max():
            # Only mark the first occurrence if there are ties
            max_indices = window_highs[window_highs == window_highs.max()].index
            if candles.index[i] == max_indices[0]:
                # Emit signal at i+right_bars (after confirmation period)
                swing_high.iloc[i + right_bars] = 1.0

        # Check if bar i is a swing low
        window_lows = candles[low_col].iloc[window_start:window_end]
        if candles[low_col].iloc[i] == window_lows.min():
            # Only mark the first occurrence if there are ties
            min_indices = window_lows[window_lows == window_lows.min()].index
            if candles.index[i] == min_indices[0]:
                # Emit signal at i+right_bars (after confirmation period)
                swing_low.iloc[i + right_bars] = 1.0

    # Create the output DataFrame
    swings = pd.DataFrame(index=candles.index)
    swings["swing_high"] = swing_high
    swings["swing_low"] = swing_low

    return swings
