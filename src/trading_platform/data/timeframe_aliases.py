"""Helpers for canonical timeframe labels and column prefixes."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

import pandas as pd

# Legacy prefixes (letter-first) mapped to canonical Pandas-style aliases (lowercase).
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
    ]
)


def _normalize_indicator_suffix(column_name: str) -> str:
    if column_name.endswith("DI+"):
        return f"{column_name[:-3]}DIplus"
    if column_name.endswith("DI-"):
        return f"{column_name[:-3]}DIminus"
    return column_name


def normalize_timeframe_prefix(column_name: str) -> str:
    """Return a column name with a canonical timeframe prefix if applicable."""

    for legacy, canonical in TIMEFRAME_PREFIX_RENAMES.items():
        legacy_prefix = f"{legacy}_"
        if column_name.startswith(legacy_prefix):
            suffix = column_name[len(legacy_prefix) :]
            return f"{canonical}_{suffix}"
    return column_name


def normalize_timeframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename timeframe-prefixed columns in a DataFrame to canonical labels."""

    rename_map: dict[str, str] = {}
    for column in df.columns:
        normalized = normalize_timeframe_prefix(column)
        normalized = _normalize_indicator_suffix(normalized)
        if normalized != column:
            rename_map[column] = normalized
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def normalize_name_sequence(columns: Iterable[str]) -> list[str]:
    """Normalize a sequence of column names (helper for metadata lists)."""

    return [
        _normalize_indicator_suffix(normalize_timeframe_prefix(column))
        for column in columns
    ]


__all__ = [
    "TIMEFRAME_PREFIX_RENAMES",
    "normalize_timeframe_columns",
    "normalize_timeframe_prefix",
    "normalize_name_sequence",
]
