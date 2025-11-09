#!/usr/bin/env python3
"""
Convert TradingView raw exports into aligned parquet snapshots for golden tests.

These parquets are pure copies of the TradingView indicator exports (no math),
ensuring the validation suite can assert that cached files stay in sync with
the original CSV downloads.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
ALIGNED_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "aligned"

TIMEFRAME_EXPORTS = {
    "1H": ("eurusd_h1_tradingview.csv", "eurusd_1h.parquet"),
    "4H": ("eurusd_h4_tradingview.csv", "eurusd_4h.parquet"),
    "1D": ("eurusd_d1_tradingview.csv", "eurusd_1d.parquet"),
}


def _load_export(csv_name: str) -> pd.DataFrame:
    path = RAW_DIR / csv_name
    if not path.exists():
        raise FileNotFoundError(f"TradingView export not found: {path}")
    df = pd.read_csv(path, parse_dates=["time"])
    if "time" not in df.columns:
        raise ValueError(f"'time' column missing from {path}")
    idx = pd.DatetimeIndex(pd.to_datetime(df["time"], utc=True), name="time")
    df = df.drop(columns=["time"]).set_index(idx).sort_index()
    return df


def _write_parquet(df: pd.DataFrame, parquet_name: str) -> Path:
    dest = ALIGNED_DIR / parquet_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest)
    return dest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeframes",
        nargs="*",
        choices=sorted(TIMEFRAME_EXPORTS.keys()),
        help="Subset of timeframes to rebuild. Defaults to all.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    targets = args.timeframes or sorted(TIMEFRAME_EXPORTS.keys())
    for timeframe in targets:
        csv_name, parquet_name = TIMEFRAME_EXPORTS[timeframe]
        df = _load_export(csv_name)
        dest = _write_parquet(df, parquet_name)
        print(
            f"Wrote {dest.relative_to(PROJECT_ROOT)} "
            f"({len(df)} rows, {len(df.columns)} columns)"
        )


if __name__ == "__main__":
    main()
