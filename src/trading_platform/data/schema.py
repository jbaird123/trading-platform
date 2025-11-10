from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_platform.data.instrument import InstrumentDefinition, SessionDefinition
from trading_platform.data.resample import resample_data
from trading_platform.data.session_metadata import extract_session

# Define the schema contract as a constant. This makes it easy to manage and reuse.
# It maps the raw column names to our desired normalized names.
COLUMN_MAP = {
    "UTCTime": "timestamp",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


def load_and_normalize_data(file_path: Path) -> tuple[pd.DataFrame, list[str]]:
    """
    Loads data from a CSV file, normalizes it according to the schema contract,
    and returns a DataFrame along with any data quality flags.

    Args:
        file_path: The path to the input CSV file.

    Returns:
        A tuple containing:
        - A pandas DataFrame with the normalized data.
        - A list of strings representing any data quality flags that were raised.
    """
    quality_flags = []

    try:
        # Faster CSV read with C engine and memory mapping
        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig",
            engine="c",
            memory_map=True,
        )
        # Normalize column names (trim whitespace)
        df.columns = [str(c).strip() for c in df.columns]

        # Accept strict normalized format or map legacy raw format.
        cols_set = set(df.columns)
        normalized_required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        if "timestamp" in cols_set:
            unknown = sorted(cols_set - normalized_required)
            missing = sorted(normalized_required - cols_set)
            if unknown or missing:
                quality_flags.append(
                    f"unexpected_columns: missing={missing} unknown={unknown}"
                )
                return pd.DataFrame(), quality_flags
        elif "UTCTime" in cols_set:
            # Map legacy raw -> normalized
            required_raw = set(COLUMN_MAP.keys())
            unknown = sorted(cols_set - required_raw)
            missing = sorted(required_raw - cols_set)
            if unknown or missing:
                quality_flags.append(
                    f"unexpected_columns: missing={missing} unknown={unknown}"
                )
                return pd.DataFrame(), quality_flags
            df = df.rename(columns=COLUMN_MAP)
        else:
            quality_flags.append("missing_timestamp")
            quality_flags.append(f"columns:{sorted(list(cols_set))}")
            return pd.DataFrame(), quality_flags

        # Ensure timestamp index in UTC; treat parse failures as errors
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="raise")
        df = df.set_index("timestamp")

        return df, quality_flags

    except Exception as e:
        # Catch any other unexpected errors during loading/processing.
        error_message = f"unexpected_error: {e}"
        quality_flags.append(error_message)
        return pd.DataFrame(), quality_flags


def resample_ohlc(
    df: pd.DataFrame,
    rule: str,
    instrument: InstrumentDefinition | None = None,
    session: SessionDefinition | None = None,
) -> pd.DataFrame:
    """Resample an OHLCV DataFrame using canonical aggregation rules."""

    resolved_session = session
    if resolved_session is None and instrument is not None:
        if instrument.sessions:
            resolved_session = instrument.sessions[0]

    if resolved_session is None:
        try:
            resolved_session = extract_session(df)
        except ValueError:
            resolved_session = None

    result = (
        resample_data(df, rule, session=resolved_session)
        if resolved_session
        else resample_data(df, rule)
    )

    if resolved_session is not None and str(rule).lower() in {"1d", "d"}:
        localized = result.tz_convert(resolved_session.close_timezone)
        localized_index = pd.DatetimeIndex(localized.index)
        normalized = _calendarize_session_close_index(
            localized_index, session_hour=resolved_session.close_time.hour
        )
        normalized = normalized.tz_convert("UTC").normalize()
        result.index = normalized

    return result


def _calendarize_session_close_index(
    index: pd.DatetimeIndex, session_hour: int
) -> pd.DatetimeIndex:
    """Convert timestamps labeled at session-close to the following calendar date.

    Some reporting paths expect daily bars to be indexed by the date whose session
    ended at the close. When a timestamp already equals the session close, shift
    it forward one calendar day; otherwise keep its calendar date.
    """

    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("index must be a DatetimeIndex")

    new_index = []
    for ts in index:
        if ts.hour == session_hour:
            calendar_date = (ts + pd.Timedelta(days=1)).date()
        else:
            calendar_date = ts.date()
        new_index.append(pd.Timestamp(calendar_date, tz=ts.tz))
    return pd.DatetimeIndex(new_index, name=index.name)
