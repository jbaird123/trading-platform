"""
Safe indicator helper functions for bias-free implementations.

These helpers make it easier to write indicators that don't have
look-ahead bias by providing common patterns with proper lagging
and windowing.
"""

from __future__ import annotations

import pandas as pd


def safe_rolling_max(series: pd.Series, window: int, lag: int = 0) -> pd.Series:
    """
    Compute rolling max without look-ahead bias.

    Args:
        series: Input series
        window: Window size
        lag: Additional lag to apply (default=0, no extra lag)

    Returns:
        Series with rolling max, properly lagged

    Example:
        >>> prices = pd.Series([1, 2, 3, 4, 5])
        >>> safe_rolling_max(prices, window=3)
        # Returns max of current + 2 previous bars
    """
    # center=False ensures only historical data is used
    rolling = series.rolling(window=window, center=False).max()

    # Apply additional lag if needed
    if lag > 0:
        rolling = rolling.shift(lag)

    return rolling


def safe_rolling_min(series: pd.Series, window: int, lag: int = 0) -> pd.Series:
    """
    Compute rolling min without look-ahead bias.

    Args:
        series: Input series
        window: Window size
        lag: Additional lag to apply (default=0)

    Returns:
        Series with rolling min, properly lagged
    """
    rolling = series.rolling(window=window, center=False).min()

    if lag > 0:
        rolling = rolling.shift(lag)

    return rolling


def safe_rolling_mean(series: pd.Series, window: int, lag: int = 0) -> pd.Series:
    """
    Compute rolling mean without look-ahead bias.

    Args:
        series: Input series
        window: Window size
        lag: Additional lag to apply (default=0)

    Returns:
        Series with rolling mean, properly lagged
    """
    rolling = series.rolling(window=window, center=False).mean()

    if lag > 0:
        rolling = rolling.shift(lag)

    return rolling


def safe_rolling_std(series: pd.Series, window: int, lag: int = 0) -> pd.Series:
    """
    Compute rolling standard deviation without look-ahead bias.

    Args:
        series: Input series
        window: Window size
        lag: Additional lag to apply (default=0)

    Returns:
        Series with rolling std, properly lagged
    """
    rolling = series.rolling(window=window, center=False).std()

    if lag > 0:
        rolling = rolling.shift(lag)

    return rolling


def safe_expanding_max(series: pd.Series, lag: int = 0) -> pd.Series:
    """
    Compute expanding max (all-time high up to current bar).

    Args:
        series: Input series
        lag: Additional lag to apply (default=0)

    Returns:
        Series with expanding max, properly lagged
    """
    expanding = series.expanding().max()

    if lag > 0:
        expanding = expanding.shift(lag)

    return expanding


def safe_expanding_min(series: pd.Series, lag: int = 0) -> pd.Series:
    """
    Compute expanding min (all-time low up to current bar).

    Args:
        series: Input series
        lag: Additional lag to apply (default=0)

    Returns:
        Series with expanding min, properly lagged
    """
    expanding = series.expanding().min()

    if lag > 0:
        expanding = expanding.shift(lag)

    return expanding


def safe_diff(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Compute difference with previous bar (always safe).

    Args:
        series: Input series
        periods: Number of periods to look back (default=1)

    Returns:
        Series with differences
    """
    return series.diff(periods=periods)


def safe_pct_change(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Compute percentage change (always safe).

    Args:
        series: Input series
        periods: Number of periods to look back (default=1)

    Returns:
        Series with percentage changes
    """
    return series.pct_change(periods=periods)


def safe_shift(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Shift series forward (creates lag).

    Args:
        series: Input series
        periods: Number of periods to shift (positive = lag)

    Returns:
        Shifted series

    Note:
        Positive periods create lag (safe).
        Negative periods look ahead (UNSAFE - raises error).
    """
    if periods < 0:
        raise ValueError(
            f"Negative shift ({periods}) looks ahead! " "Use positive values for lag."
        )

    return series.shift(periods)


def validate_no_center_rolling(
    rolling_obj: pd.core.window.rolling.Rolling,
) -> None:
    """
    Validate that a rolling window does not use center=True.

    Args:
        rolling_obj: pandas Rolling object

    Raises:
        ValueError: If center=True is detected

    Example:
        >>> rolling = series.rolling(20, center=False)
        >>> validate_no_center_rolling(rolling)  # OK
        >>> rolling = series.rolling(20, center=True)
        >>> validate_no_center_rolling(rolling)  # Raises ValueError
    """
    # Access the center attribute from the rolling object
    if hasattr(rolling_obj, "center") and rolling_obj.center:
        raise ValueError(
            "Rolling window with center=True detected! "
            "This causes look-ahead bias. Use center=False."
        )


def hhv(series: pd.Series, length: int) -> pd.Series:
    """
    Highest High Value (rolling max) - alias for clarity.

    Args:
        series: Input series (typically 'high' prices)
        length: Lookback window

    Returns:
        Rolling maximum over window
    """
    return safe_rolling_max(series, window=length)


def llv(series: pd.Series, length: int) -> pd.Series:
    """
    Lowest Low Value (rolling min) - alias for clarity.

    Args:
        series: Input series (typically 'low' prices)
        length: Lookback window

    Returns:
        Rolling minimum over window
    """
    return safe_rolling_min(series, window=length)


def donchian_channels(highs: pd.Series, lows: pd.Series, length: int) -> pd.DataFrame:
    """
    Donchian Channels (upper/lower bands from rolling high/low).

    Args:
        highs: High prices
        lows: Low prices
        length: Lookback period

    Returns:
        DataFrame with 'upper' and 'lower' columns
    """
    upper = safe_rolling_max(highs, window=length)
    lower = safe_rolling_min(lows, window=length)

    return pd.DataFrame({"upper": upper, "lower": lower}, index=highs.index)
