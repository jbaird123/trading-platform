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

    # Set up resampling kwargs
    resample_kwargs = {"label": "left"}
    if rule.upper() in ("D", "1D") and instrument and instrument.sessions:
        # Use the hour from the first session definition as the origin for daily bars
        session_hour = instrument.sessions[0].close_time.hour
        # Set origin to the session close time on epoch day with UTC timezone
        resample_kwargs["origin"] = pd.Timestamp(f"1970-01-01 {session_hour:02d}:00:00", tz="UTC")

    out = df.resample(rule, **resample_kwargs).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    out = out.dropna(how="any")
    
    # For daily resampling with session offset, normalize timestamps to calendar dates
    if rule.upper() in ("D", "1D") and instrument and instrument.sessions:
        # Convert index to calendar date with 00:00:00 time
        session_hour = instrument.sessions[0].close_time.hour
        new_index = []
        for ts in out.index:
            # The resampled timestamp at session hour represents the trading day ending at that time
            # For example, 2022-12-31 17:00 represents data ending at 17:00 on 2022-12-31,
            # which should be labeled as the 2023-01-01 calendar day (next day)
            # With origin parameter set correctly, timestamps should always be at session_hour
            if ts.hour == session_hour:
                calendar_date = (ts + pd.Timedelta(days=1)).date()
            else:
                # Defensive fallback: if timestamp hour doesn't match session hour,
                # use the timestamp's date as-is
                calendar_date = ts.date()
            new_index.append(pd.Timestamp(calendar_date, tz=ts.tz))
        out.index = pd.DatetimeIndex(new_index, name=out.index.name)
    
    return out
