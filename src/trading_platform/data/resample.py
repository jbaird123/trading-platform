"""Resampling utilities for multi-timeframe feature computation.

This module provides utilities for resampling OHLCV data to higher
timeframes, used by the feature engine to compute contextual features
at multiple timeframes (e.g., 15m strategy with 1H contextual features).
"""

from __future__ import annotations

import warnings

import pandas as pd


def resample_data(data: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV data to a higher timeframe.

    This function resamples OHLCV data using canonical aggregation rules:
    - open: first
    - high: max
    - low: min
    - close: last
    - volume: sum

    The function uses `label="right", closed="right"` to align with
    TradingView's bar labeling convention.

    Args:
        data: DataFrame with DatetimeIndex and OHLCV columns
        rule: Resampling frequency (e.g., "1H", "4H", "1D")

    Returns:
        Resampled DataFrame with complete bars only (partial bars dropped)

    Raises:
        TypeError: If data.index is not a DatetimeIndex
        ValueError: If rule is not a valid pandas frequency string

    Warns:
        UserWarning: If resampling produces entirely NaN data
    """
    # Validate index type
    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError(f"Data index must be a DatetimeIndex, got {type(data.index)}")

    # Define aggregation logic
    agg_logic = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    # Normalize rule to lowercase to avoid pandas deprecation warnings
    rule = str(rule).lower()

    # Validate that the rule is parsable by attempting a dummy offset
    try:
        pd.tseries.frequencies.to_offset(rule)
    except ValueError as e:
        raise ValueError(f"Invalid frequency rule: {rule}") from e

    # Perform resampling with closed="left", label="right" to align
    # with TradingView-style bar labeling convention:
    # - closed="left": bar includes start time, excludes end time
    # - label="right": bar is labeled at the close (end of period)
    resampled = data.resample(rule, closed="left", label="right").agg(
        agg_logic  # type: ignore[arg-type]
    )

    # Check if OHLC columns are entirely NaN (sparse resampling)
    # Note: volume sum of NaN is 0, so we check OHLC columns only
    ohlc_columns = ["open", "high", "low", "close"]
    available_ohlc = [col for col in ohlc_columns if col in resampled.columns]
    # Check if all OHLC columns are entirely NaN
    all_nan = (
        all(resampled[col].isna().all() for col in available_ohlc)
        if available_ohlc
        else False
    )
    if all_nan:
        warnings.warn(
            f"Resampling to {rule} produced entirely NaN data. "
            "This may indicate the source timeframe is too coarse for the "
            "target timeframe, leading to NaN propagation when forward-filling.",
            UserWarning,
            stacklevel=2,
        )

    # Drop rows with any NaN values
    result = resampled.dropna()

    # Drop the last row if it represents a partial/incomplete bucket
    # A bucket is incomplete if the last source bar doesn't reach the
    # expected end of the bucket. With closed='left', a bucket labeled
    # at time T contains data from T-period to T (exclusive), so the
    # last bar in a complete bucket should be at T - source_freq.
    if len(result) > 0 and len(data) > 1:
        # Infer source frequency from the first two bars
        source_freq = data.index[1] - data.index[0]
        last_bucket_label = result.index[-1]
        # For a complete bucket, the last source bar should be one
        # source period before the bucket label
        expected_last_bar = last_bucket_label - source_freq
        # If our actual last bar is before the expected, drop the bucket
        if data.index[-1] < expected_last_bar:
            result = result.iloc[:-1]

    return result
