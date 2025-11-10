#!/usr/bin/env python3
"""
Build TradingView multi-timeframe feature caches for golden tests.

Each parquet embeds higher timeframe features into the base timeframe while
explicitly labeling that the values become available only after their source
bar closes. This mirrors the no-look-ahead alignment enforced inside the
platform cache builder.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

import pandas as pd
from trading_platform.data.resample import timeframe_to_timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
ALIGNED_DIR = (
    PROJECT_ROOT
    / "data"
    / "dvc"
    / "golden"
    / "features"
    / "aligned_available_after_close"
)

OHLC_COLUMNS = ["open", "high", "low", "close", "volume"]
TIMEFRAME_EXPORTS = OrderedDict(
    [
        (
            "1H",
            ("eurusd_h1_tradingview.csv", "eurusd_1h_available_after_close.parquet"),
        ),
        (
            "4H",
            ("eurusd_h4_tradingview.csv", "eurusd_4h_available_after_close.parquet"),
        ),
        (
            "1D",
            ("eurusd_d1_tradingview.csv", "eurusd_1d_available_after_close.parquet"),
        ),
    ]
)


def _load_export(csv_name: str) -> pd.DataFrame:
    path = RAW_DIR / csv_name
    if not path.exists():
        raise FileNotFoundError(f"TradingView export not found: {path}")
    df = pd.read_csv(path, parse_dates=["time"])
    if "time" not in df.columns:
        raise ValueError(f"'time' column missing from {path}")
    idx = pd.DatetimeIndex(pd.to_datetime(df["time"], utc=True), name="time")
    df = (
        df.drop(columns=["time"])
        .set_index(idx)
        .sort_index()
        .drop(columns=OHLC_COLUMNS + ["timestamp"], errors="ignore")
    )
    return df


def _write_parquet(df: pd.DataFrame, parquet_name: str) -> Path:
    dest = ALIGNED_DIR / parquet_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    return dest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeframes",
        nargs="*",
        choices=list(TIMEFRAME_EXPORTS.keys()),
        help="Subset of timeframes to rebuild. Defaults to all.",
    )
    return parser.parse_args()


def _build_embedded_frames(
    target_timeframes: list[str],
) -> dict[str, pd.DataFrame]:
    raw_features: dict[str, pd.DataFrame] = {
        tf: _load_export(TIMEFRAME_EXPORTS[tf][0]) for tf in target_timeframes
    }
    td_minutes = {
        tf: timeframe_to_timedelta(tf).total_seconds() / 60 for tf in raw_features
    }

    embedded: dict[str, pd.DataFrame] = {}
    ordered_targets = sorted(target_timeframes, key=lambda tf: td_minutes[tf])

    for base_tf in ordered_targets:
        base_index = raw_features[base_tf].index
        base_available_index = base_index + timeframe_to_timedelta(base_tf)
        base_df = raw_features[base_tf].reindex(base_index)
        base_df.index = base_available_index

        for higher_tf in ordered_targets:
            if td_minutes[higher_tf] <= td_minutes[base_tf]:
                continue
            higher_df = raw_features[higher_tf].copy()
            higher_df.index = higher_df.index + timeframe_to_timedelta(higher_tf)
            aligned = higher_df.reindex(base_available_index, method="ffill")
            base_df = pd.concat([base_df, aligned], axis=1)

        embedded[base_tf] = base_df
    return embedded


def _finalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    final_df = df.reset_index()
    index_name = df.index.name or "index"
    final_df = final_df.rename(columns={index_name: "available_at"})
    cols = final_df.columns.tolist()
    ordered_cols = ["available_at"] + [c for c in cols if c != "available_at"]
    return final_df[ordered_cols]


def main() -> None:
    args = _parse_args()
    targets = args.timeframes or list(TIMEFRAME_EXPORTS.keys())
    embedded = _build_embedded_frames(targets)

    for timeframe in targets:
        _, parquet_name = TIMEFRAME_EXPORTS[timeframe]
        df = embedded[timeframe]
        final_df = _finalize_frame(df)
        dest = _write_parquet(final_df, parquet_name)
        print(
            f"Wrote {dest.relative_to(PROJECT_ROOT)} "
            f"({len(df)} rows, {len(df.columns)} columns)"
        )


if __name__ == "__main__":
    main()
