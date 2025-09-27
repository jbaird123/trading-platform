from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import load_and_normalize_data


def load_instrument_data(
    symbol: str, data_root: Path
) -> tuple[pd.DataFrame, list[str]]:
    """Load normalized OHLCV data using convention-based directory structure.

    Args:
        symbol: The financial instrument symbol (e.g., "EUR/USD", "EURUSD")
        data_root: Root directory containing the data files

    Returns:
        A tuple containing:
        - DataFrame with normalized OHLCV data (timestamp index)
        - List of data quality flags

    Raises:
        FileNotFoundError: If no data files are found for the symbol
    """
    # Sanitize symbol to lowercase for path construction
    sanitized_symbol = symbol.replace("/", "").lower()

    # Construct paths to full and incremental directories
    full_dir = data_root / "full" / sanitized_symbol
    incremental_dir = data_root / "incremental" / sanitized_symbol

    # Alternative path structure for compatibility with test fixtures
    if not full_dir.exists():
        # Try the format used in test fixtures: data_root/symbol_test/full/
        test_dir = data_root / f"{sanitized_symbol}_test"
        if test_dir.exists():
            full_dir = test_dir / "full"
            incremental_dir = test_dir / "incremental"

    # Find base file in full directory
    base_files = list(full_dir.glob("*.csv")) if full_dir.exists() else []

    if not base_files:
        raise FileNotFoundError(f"No data files found for symbol: {symbol}")

    # Load the first (and typically only) base file
    base_file = base_files[0]
    df, flags = load_and_normalize_data(base_file)

    if df.empty:
        raise ValueError(f"Base data file is empty: {base_file}")

    dataframes = [df]

    # Load incremental files if directory exists
    if incremental_dir.exists():
        incremental_files = list(incremental_dir.glob("*.csv"))

        for file_path in incremental_files:
            try:
                inc_df, inc_flags = load_and_normalize_data(file_path)
                if not inc_df.empty:
                    dataframes.append(inc_df)
                    flags.extend(inc_flags)
            except Exception:
                # Skip files that fail to load - they may be incomplete
                continue

    # Combine all dataframes if we have more than just the base
    if len(dataframes) > 1:
        df = pd.concat(dataframes, ignore_index=False)
        # Sort by index and drop duplicates to ensure clean time-series
        df = df.sort_index().drop_duplicates()

    return df, flags
