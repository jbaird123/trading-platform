"""Utilities for computing canonical bar open/close windows."""

from __future__ import annotations

from datetime import time

import pandas as pd

from trading_platform.data.instrument import SessionDefinition
from trading_platform.data.resample import timeframe_to_timedelta


def _ensure_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    dt_index = pd.DatetimeIndex(index)
    if dt_index.tz is None:
        return dt_index.tz_localize("UTC")
    return dt_index.tz_convert("UTC")


def _session_close_offset(session: SessionDefinition | None) -> pd.Timedelta:
    if session is None:
        return pd.Timedelta(0)
    close_time: time = session.close_time
    return pd.Timedelta(
        hours=close_time.hour,
        minutes=close_time.minute,
        seconds=close_time.second,
    )


def compute_bar_close_index(
    open_index: pd.Index,
    timeframe: str,
    session: SessionDefinition | None = None,
) -> pd.DatetimeIndex:
    """
    Return timestamps representing when each bar is fully closed.

    Args:
        open_index: Index of bar start timestamps (typically from raw CSV).
        timeframe: Pandas offset string (e.g., '1H', '4H', '1D').
        session: Optional instrument session definition for day-level bars.
    """

    utc_open = _ensure_utc_index(open_index)
    tf_lower = timeframe.lower()
    delta = timeframe_to_timedelta(timeframe)

    if session and tf_lower.endswith("d"):
        localized = utc_open.tz_convert(session.close_timezone)
        shifted = localized + pd.DateOffset(days=1)
        normalized = shifted.normalize()
        offset = _session_close_offset(session)
        close_local = normalized + offset
        return close_local.tz_convert("UTC")

    return utc_open + delta


def compute_bar_window_columns(
    open_index: pd.Index,
    timeframe: str,
    session: SessionDefinition | None = None,
) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]:
    """
    Compute canonical bar_open, bar_close, and lookup timestamps.

    Returns:
        Tuple of (bar_open, bar_close, bar_lookup_key) as UTC DateTimeIndexes.
    """

    close_index = compute_bar_close_index(open_index, timeframe, session)
    delta = timeframe_to_timedelta(timeframe)
    bar_open = close_index - delta
    bar_lookup = _ensure_utc_index(open_index)
    return bar_open, close_index, bar_lookup


__all__ = [
    "compute_bar_close_index",
    "compute_bar_window_columns",
]
