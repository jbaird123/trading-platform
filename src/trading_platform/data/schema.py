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
        df = pd.read_csv(file_path)

        # --- Validation Step 1: Check for the essential timestamp column ---
        if "UTCTime" not in df.columns:
            quality_flags.append("missing_timestamp")
            # If the timestamp is missing, the data is unusable.
            # So return an empty DataFrame.
            return pd.DataFrame(), quality_flags

        # --- Normalization Step 1: Rename columns to snake_case ---
        df = df.rename(columns=COLUMN_MAP)

        # --- Normalization Step 2: Convert timestamp and set as index ---
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

        return df, quality_flags

    except Exception as e:
        # Catch any other unexpected errors during loading/processing.
        error_message = f"unexpected_error: {e}"
        quality_flags.append(error_message)
        return pd.DataFrame(), quality_flags
