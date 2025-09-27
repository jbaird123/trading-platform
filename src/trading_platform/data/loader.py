from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

import pandas as pd

from ..core.utils import normalize_symbol
from .instrument import InstrumentDefinition, get_instrument_definition
from .schema import load_and_normalize_data, resample_ohlc


def load_from_catalog(
    data_request: dict[str, Any],
    catalog_path: Path | None = None,
) -> tuple[pd.DataFrame, list[str], InstrumentDefinition]:
    """Load normalized OHLCV from a symbol catalog using a data request.

    data_request keys:
    - symbol: str (required)
    - timeframe: str (e.g., "1H")
    - start: ISO date/time string
    - end: ISO date/time string
    """
    if not isinstance(data_request, dict):
        raise ValueError("data_request must be a dict")
    symbol = str(data_request.get("symbol")) if data_request.get("symbol") else ""
    if not symbol:
        raise ValueError("data_request.symbol is required")

    # Normalize symbol to canonical format for catalog lookup
    canonical_symbol = normalize_symbol(symbol)

    # Default catalog path relative to repo root
    cpath = catalog_path or Path("config/data_catalog.yaml")
    if not cpath.exists():
        raise FileNotFoundError(f"data catalog not found: {cpath}")

    import yaml

    catalog = yaml.safe_load(cpath.read_text()) or {}
    entry = (catalog.get(canonical_symbol) or {}) if isinstance(catalog, dict) else {}
    csv_path = entry.get("csv_path") if isinstance(entry, dict) else None
    if not csv_path:
        raise ValueError(f"symbol not in catalog: {symbol}")

    # Get instrument definition after validating symbol is in catalog
    instrument = get_instrument_definition(symbol)

    # Load base file
    base_path = Path(str(csv_path)).expanduser()
    df, flags = load_and_normalize_data(base_path)

    # Fail fast if loader detected unusable data
    if df.empty:
        msg = (
            "Loaded data is empty or missing timestamp. "
            f"Flags: {flags}. Ensure CSV has 'timestamp' plus OHLCV columns."
        )
        raise ValueError(msg)

    # Load incremental files if they exist
    dataframes = [df]

    # Construct path to incremental directory
    # Assume base file is in 'data/full/' and incremental is in
    # 'data/incremental/{symbol}/'
    base_dir = base_path.parent
    data_root = base_dir.parent if base_dir.name == "full" else base_dir
    incremental_dir = data_root / "incremental" / canonical_symbol.lower()

    if incremental_dir.exists():
        # Find all CSV files in incremental directory
        pattern = str(incremental_dir / "*.csv")
        incremental_files = glob.glob(pattern)

        # Load each incremental file
        for file_path in incremental_files:
            try:
                inc_df, inc_flags = load_and_normalize_data(Path(file_path))
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

    # Resample if timeframe provided
    tf = data_request.get("timeframe")
    if tf:
        df = resample_ohlc(df, str(tf), instrument)

    # Filter by start/end AFTER resample for index alignment
    start = data_request.get("start")
    end = data_request.get("end")
    if start:
        df = df.loc[pd.to_datetime(start, utc=True) :]  # noqa: E203
    if end:
        df = df.loc[: pd.to_datetime(end, utc=True)]

    return df, flags, instrument
