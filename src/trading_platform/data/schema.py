from __future__ import annotations

from pathlib import Path

import pandas as pd

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
        # Robust read: handle BOM and auto-detect common delimiters
        df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8-sig")
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

        # Ensure timestamp index in UTC
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

        return df, quality_flags

    except Exception as e:
        # Catch any other unexpected errors during loading/processing.
        error_message = f"unexpected_error: {e}"
        quality_flags.append(error_message)
        return pd.DataFrame(), quality_flags


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample an OHLCV DataFrame using canonical aggregation rules.

    - open: first
    - high: max
    - low: min
    - close: last
    - volume: sum
    """
    # Normalize rule to lowercase (avoid pandas deprecation warnings)
    rule = str(rule).lower()
    out = df.resample(rule).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    return out.dropna(how="any")
