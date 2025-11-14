"""Resampling utilities for multi-timeframe feature computation.

This module provides utilities for resampling OHLCV data to higher
timeframes, used by the feature engine to compute contextual features
at multiple timeframes (e.g., 15m strategy with 1H contextual features).
"""

from __future__ import annotations

import re
import warnings
from typing import Mapping, cast

import pandas as pd
from pandas.tseries.frequencies import to_offset
from pandas.tseries.offsets import Week

from trading_platform.data.instrument import SessionDefinition
from trading_platform.data.session_metadata import (
    ALIGNED_TO_CLOSE_ATTR,
    annotate_session,
    extract_session,
)


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
            normalized = f"{value}W"
    return to_offset(normalized)


def timeframe_to_timedelta(rule: str) -> pd.Timedelta:
    """Return the duration represented by a timeframe string."""
    offset = _timeframe_to_offset(rule)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        delta = getattr(offset, "delta", None)
    if isinstance(delta, pd.Timedelta):
        return delta
    try:
        nanos = getattr(offset, "nanos", None)
    except ValueError:
        nanos = None
    if nanos is not None and nanos != 0:
        return pd.Timedelta(nanos, unit="ns")
    if isinstance(offset, Week):
        return pd.Timedelta(days=7 * offset.n)
    return pd.to_timedelta(offset.freqstr)


def resample_data(
    data: pd.DataFrame,
    rule: str,
    session: SessionDefinition | None = None,
) -> pd.DataFrame:
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

    resolved_session = session
    if resolved_session is None:
        try:
            resolved_session = extract_session(data)
        except ValueError:
            resolved_session = None

    agg_logic = _build_agg_logic(data)
    if resolved_session is None:
        return _naive_resample(data, rule, agg_logic)
    return _session_resample(data, rule, agg_logic, resolved_session)


def _build_agg_logic(df: pd.DataFrame) -> dict[str, str]:
    logic: dict[str, str] = {}
    if "open" in df.columns:
        logic["open"] = "first"
    if "high" in df.columns:
        logic["high"] = "max"
    if "low" in df.columns:
        logic["low"] = "min"
    if "close" in df.columns:
        logic["close"] = "last"
    if "volume" in df.columns:
        logic["volume"] = "sum"
    if not logic:
        raise ValueError("Cannot resample DataFrame without OHLC/volume columns.")
    return logic


def _session_resample(
    data: pd.DataFrame,
    rule: str,
    agg_logic: dict[str, str],
    session: SessionDefinition,
) -> pd.DataFrame:
    try:
        offset = _timeframe_to_offset(rule)
    except ValueError as exc:
        raise ValueError(f"Invalid frequency rule: {rule}") from exc

    freqstr = offset.freqstr.lower()

    local_df = data.tz_convert(session.close_timezone)
    tz_index = pd.DatetimeIndex(local_df.index)
    naive_local = local_df.copy()
    naive_local.index = pd.DatetimeIndex(tz_index.tz_localize(None), name=tz_index.name)

    session_offset = pd.Timedelta(
        hours=session.close_time.hour,
        minutes=session.close_time.minute,
        seconds=session.close_time.second,
    )
    shifted = naive_local.copy()
    shifted.index = pd.DatetimeIndex(shifted.index - session_offset)

    agg_mapping = cast("Mapping[str, str]", agg_logic)
    resampled = shifted.resample(freqstr, closed="left", label="left").agg(agg_mapping)  # type: ignore[arg-type]
    resampled = resampled.dropna(how="any")

    resampled_index = pd.DatetimeIndex(resampled.index + session_offset)
    resampled_index = resampled_index.tz_localize(
        session.close_timezone, ambiguous="infer", nonexistent="shift_forward"
    )
    resampled_index = resampled_index.tz_convert("UTC")
    resampled.index = resampled_index

    if len(resampled) > 0 and len(data) > 1:
        source_freq = data.index[1] - data.index[0]
        bucket_duration = timeframe_to_timedelta(freqstr)
        last_bucket_close = resampled.index[-1]
        expected_last_source_bar = last_bucket_close - bucket_duration + source_freq
        if data.index[-1] < expected_last_source_bar:
            resampled = resampled.iloc[:-1]

    annotate_session(resampled, session)
    resampled.attrs[ALIGNED_TO_CLOSE_ATTR] = True
    return resampled


def _naive_resample(
    data: pd.DataFrame,
    rule: str,
    agg_logic: dict[str, str],
) -> pd.DataFrame:
    try:
        offset = _timeframe_to_offset(rule)
    except ValueError as exc:
        raise ValueError(f"Invalid frequency rule: {rule}") from exc
    freqstr = offset.freqstr
    agg_mapping = cast("Mapping[str, str]", agg_logic)
    resampled = data.resample(freqstr, closed="left", label="left").agg(agg_mapping)  # type: ignore[arg-type]
    resampled = resampled.dropna(how="any")
    if len(resampled) > 0 and len(data) > 1:
        source_freq = data.index[1] - data.index[0]
        bucket_duration = timeframe_to_timedelta(freqstr)
        last_bucket_start = resampled.index[-1]
        expected_last_bar = last_bucket_start + bucket_duration - source_freq
        if data.index[-1] < expected_last_bar:
            resampled = resampled.iloc[:-1]
    return resampled
