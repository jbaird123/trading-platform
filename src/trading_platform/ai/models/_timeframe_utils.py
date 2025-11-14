"""Helpers for handling timeframe-derived feature columns."""

from __future__ import annotations

import pandas as pd


def _timeframe_token_to_minutes(token: str) -> int:
    """Convert tokens such as 'm15', 'h4', 'd1', '15min', '1h' to minutes."""

    normalized = token.strip().lower()

    if not normalized:
        raise ValueError("Empty timeframe token")

    # Forms like '15min'
    if normalized.endswith("min"):
        value = normalized[:-3]
        if value.isdigit():
            return int(value)
        raise ValueError(f"Invalid minute token: {token!r}")

    # Forms like '1h', '4h'
    if normalized.endswith("h"):
        value = normalized[:-1]
        if value.isdigit():
            return int(value) * 60
        raise ValueError(f"Invalid hour token: {token!r}")

    # Forms like '1d'
    if normalized.endswith("d"):
        value = normalized[:-1]
        if value.isdigit():
            return int(value) * 1440
        raise ValueError(f"Invalid day token: {token!r}")

    # Prefixed forms like 'm15', 'h4', 'd1'
    prefix = normalized[0]
    value = normalized[1:]

    if prefix == "m" and value.isdigit():
        return int(value)
    if prefix == "h" and value.isdigit():
        return int(value) * 60
    if prefix == "d" and value.isdigit():
        return int(value) * 1440

    raise ValueError(f"Unrecognized timeframe token: {token!r}")


def timeframe_to_minutes(timeframe: str) -> int:
    """Convert general timeframe string to minutes."""

    return _timeframe_token_to_minutes(timeframe)


def _extract_global_feature_minutes(column: str) -> int | None:
    """Extract timeframe minutes from a global feature column name."""

    marker = "_global_features_"
    if marker not in column:
        return None

    suffix = column.split(marker, 1)[1]
    if not suffix:
        return None

    token = suffix.split("_", 1)[0]
    try:
        return _timeframe_token_to_minutes(token)
    except ValueError:
        return None


def drop_lower_timeframe_global_features(
    df: pd.DataFrame, execution_timeframe: str
) -> pd.DataFrame:
    """Drop global feature columns whose timeframe is lower than execution."""

    exec_minutes = timeframe_to_minutes(execution_timeframe)

    cols_to_drop: list[str] = []
    for column in df.columns:
        minutes = _extract_global_feature_minutes(column)
        if minutes is not None and minutes < exec_minutes:
            cols_to_drop.append(column)

    if not cols_to_drop:
        return df

    return df.drop(columns=cols_to_drop, errors="ignore")
