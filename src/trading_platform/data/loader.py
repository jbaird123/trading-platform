from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .schema import load_and_normalize_data, resample_ohlc


def load_from_catalog(
    data_request: dict[str, Any],
    catalog_path: Path | None = None,
) -> tuple[pd.DataFrame, list[str]]:
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

    # Default catalog path relative to repo root
    cpath = catalog_path or Path("config/data_catalog.yaml")
    if not cpath.exists():
        raise FileNotFoundError(f"data catalog not found: {cpath}")

    import yaml  # type: ignore[import-untyped]

    catalog = yaml.safe_load(cpath.read_text()) or {}
    entry = (catalog.get(symbol) or {}) if isinstance(catalog, dict) else {}
    csv_path = entry.get("csv_path") if isinstance(entry, dict) else None
    if not csv_path:
        raise ValueError(f"symbol not in catalog: {symbol}")

    df, flags = load_and_normalize_data(Path(str(csv_path)).expanduser())

    # Fail fast if loader detected unusable data
    if df.empty:
        msg = (
            "Loaded data is empty or missing timestamp. "
            f"Flags: {flags}. Ensure CSV has 'timestamp' plus OHLCV columns."
        )
        raise ValueError(msg)

    # Resample if timeframe provided
    tf = data_request.get("timeframe")
    if tf:
        df = resample_ohlc(df, str(tf))

    # Filter by start/end AFTER resample for index alignment
    start = data_request.get("start")
    end = data_request.get("end")
    if start:
        df = df.loc[pd.to_datetime(start, utc=True) :]  # noqa: E203
    if end:
        df = df.loc[: pd.to_datetime(end, utc=True)]

    return df, flags
