from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_platform.data.instrument import InstrumentDefinition

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


def _calendarize_session_close_index(
    index: pd.DatetimeIndex, session_hour: int
) -> pd.DatetimeIndex:
    """Convert resampled timestamps to calendar dates.

    pandas uses the session close time as the bin label when we resample with an
    origin offset. For reporting we want each bar labelled with the calendar date
    that ended at the session close. If a timestamp does not align with the
    expected hour (which can happen with malformed data or unexpected resample
    behaviour) we fall back to the timestamp's own date.
    """

    new_index = []
    for ts in index:
        if ts.hour == session_hour:
            calendar_date = (ts + pd.Timedelta(days=1)).date()
        else:
            calendar_date = ts.date()
        new_index.append(pd.Timestamp(calendar_date, tz=ts.tz))
    return pd.DatetimeIndex(new_index, name=index.name)


def resample_ohlc(
    df: pd.DataFrame, rule: str, instrument: InstrumentDefinition | None = None
) -> pd.DataFrame:
    """Resample an OHLCV DataFrame using canonical aggregation rules.

    - open: first
    - high: max
    - low: min
    - close: last
    - volume: sum

    For daily resampling ('D' or '1D'), uses the session close time from the
    instrument definition to group data by trading day.
    """
    # Normalize rule to lowercase (avoid pandas deprecation warnings)
    rule = str(rule).lower()

    # Set up resampling parameters
    if rule.upper() in ("D", "1D") and instrument and instrument.sessions:
        # Use the hour from the first session definition as the origin for daily bars
        session_hour = instrument.sessions[0].close_time.hour
        # Set origin to the session close time on epoch day with UTC timezone
        origin_ts = pd.Timestamp(f"1970-01-01 {session_hour:02d}:00:00", tz="UTC")
        out = df.resample(rule, label="left", origin=origin_ts).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
    else:
        out = df.resample(rule, label="left").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )

    out = out.dropna(how="any")

    # For daily resampling with session offset, normalize timestamps to calendar dates
    if rule.upper() in ("D", "1D") and instrument and instrument.sessions:
        session_hour = instrument.sessions[0].close_time.hour
        # Type assertion: after resampling, index should be DatetimeIndex
        datetime_index = pd.DatetimeIndex(out.index)
        out.index = _calendarize_session_close_index(datetime_index, session_hour)

    return out
