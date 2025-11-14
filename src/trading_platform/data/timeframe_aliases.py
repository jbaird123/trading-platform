"""Helpers for canonical timeframe labels and column prefixes."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

import pandas as pd

# Legacy prefixes (letter-first) mapped to canonical pandas-style aliases (lowercase).
TIMEFRAME_PREFIX_RENAMES: OrderedDict[str, str] = OrderedDict(
    [
        ("m1", "1min"),
        ("m5", "5min"),
        ("m15", "15min"),
        ("m30", "30min"),
        ("h1", "1h"),
        ("h2", "2h"),
        ("h4", "4h"),
        ("d1", "1d"),
        ("w1", "1w"),
    ]
)


def _normalize_indicator_suffix(column_name: str) -> str:
    if column_name.endswith("DI+"):
        return f"{column_name[:-3]}DIplus"
    if column_name.endswith("DI-"):
        return f"{column_name[:-3]}DIminus"
    return column_name


def canonicalize_timeframe(timeframe: str | None) -> str | None:
    """Return the canonical pandas-style form for a timeframe string."""

    if timeframe is None:
        return None
    normalized = timeframe.strip().lower()
    return TIMEFRAME_PREFIX_RENAMES.get(normalized, normalized)


def canonicalize_column_name(column_name: str) -> str:
    """Return column_name with the canonical timeframe prefix if applicable."""

    if "_" not in column_name:
        return column_name
    prefix, suffix = column_name.split("_", 1)
    canonical_prefix = canonicalize_timeframe(prefix)
    if canonical_prefix and canonical_prefix != prefix.lower():
        return f"{canonical_prefix}_{suffix}"
    return column_name


def normalize_timeframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename timeframe-prefixed columns in a DataFrame to canonical labels."""

    rename_map: dict[str, str] = {}
    for column in df.columns:
        normalized = canonicalize_column_name(column)
        normalized = _normalize_indicator_suffix(normalized)
        if normalized != column:
            rename_map[column] = normalized
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def normalize_name_sequence(columns: Iterable[str]) -> list[str]:
    """Normalize a sequence of column names (helper for metadata lists)."""

    return [
        _normalize_indicator_suffix(canonicalize_column_name(column))
        for column in columns
    ]


__all__ = [
    "TIMEFRAME_PREFIX_RENAMES",
    "canonicalize_timeframe",
    "canonicalize_column_name",
    "normalize_timeframe_columns",
    "normalize_name_sequence",
]
