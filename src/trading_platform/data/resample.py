"""Resampling utilities for multi-timeframe feature computation.

This module provides utilities for resampling OHLCV data to higher
timeframes, used by the feature engine to compute contextual features
at multiple timeframes (e.g., 15m strategy with 1H contextual features).
"""

from __future__ import annotations

import re
import warnings

import pandas as pd
from pandas.tseries.frequencies import to_offset


def _timeframe_to_offset(rule: str) -> pd.tseries.offsets.BaseOffset:
    """Convert timeframe string to pandas offset."""
    normalized = str(rule).strip()
    match = re.fullmatch(r"(\d+)\s*([A-Za-z]+)", normalized)
    if match:
        value, unit = match.groups()
        unit_lower = unit.lower()
        if unit_lower in {"min", "t"}:
            normalized = f"{value}min"
        elif unit_lower == "h":
            normalized = f"{value}h"
        elif unit_lower == "d":
            normalized = f"{value}d"
        elif unit_lower == "w":
            normalized = f"{value}w"
    return to_offset(normalized)


def timeframe_to_timedelta(rule: str) -> pd.Timedelta:
    """Return the duration represented by a timeframe string."""
    offset = _timeframe_to_offset(rule)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        delta = getattr(offset, "delta", None)
    if isinstance(delta, pd.Timedelta):
        return delta
    nanos = getattr(offset, "nanos", None)
    if nanos is not None:
        return pd.Timedelta(nanos, unit="ns")
    return pd.to_timedelta(offset.freqstr)


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

    # Validate and obtain canonical frequency
    try:
        offset = _timeframe_to_offset(rule)
    except ValueError as e:
        raise ValueError(f"Invalid frequency rule: {rule}") from e

    freqstr = offset.freqstr

    # Perform resampling with closed="left", label="right" to align
    # with TradingView-style bar labeling convention:
    # - closed="left": bar includes start time, excludes end time
    # - label="right": bar is labeled at the close (end of period)
    resampled = data.resample(freqstr, closed="left", label="left").agg(
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
        # If all OHLC values are NaN, treat as empty result to avoid noisy warnings.
        return resampled.iloc[0:0]

    # Drop rows with any NaN values
    result = resampled.dropna()

    # Drop the last row if it represents a partial/incomplete bucket.
    # With label='left', a bucket labeled at time T covers [T, T+period),
    # so we need source data up to bucket_end - base_freq to keep it.
    if len(result) > 0 and len(data) > 1:
        # Infer source frequency from the first two bars
        source_freq = data.index[1] - data.index[0]
        bucket_duration = timeframe_to_timedelta(freqstr)
        last_bucket_start = result.index[-1]
        expected_last_bar = last_bucket_start + bucket_duration - source_freq
        if data.index[-1] < expected_last_bar:
            result = result.iloc[:-1]

    return result
