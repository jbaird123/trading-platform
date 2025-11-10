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
import hashlib
import json
import shutil
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
from trading_platform.core.global_features_cache import build_global_feature_caches
from trading_platform.data.instrument import get_instrument_definition
from trading_platform.data.resample import timeframe_to_timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
CONFIG_PATH = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "global.yaml"
DATA_ROOT = PROJECT_ROOT / "data" / "dvc" / "golden" / "ohlcv" / "tradingview"
SYMBOL = "EUR/USD"
SYMBOL_SLUG = "eurusd"
PURE_GOLDEN_DIR = (
    PROJECT_ROOT
    / "data"
    / "dvc"
    / "golden"
    / "features"
    / "tradingview"
    / "cache"
    / SYMBOL_SLUG
)
TEST_CACHE_ROOT = PROJECT_ROOT / "data" / "dvc" / "golden"
TIMESTAMP_COLUMN = "available_at"
INSTRUMENT = get_instrument_definition(SYMBOL)
SESSION = INSTRUMENT.sessions[0] if INSTRUMENT.sessions else None

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
PARQUET_FILENAMES = {"1H": "1h.parquet", "4H": "4h.parquet", "1D": "1d.parquet"}


def _config_hash() -> str:
    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()


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


def _align_available_index(
    index: pd.DatetimeIndex,
    timeframe: str,
) -> pd.DatetimeIndex:
    """Return timestamps representing when the bar finishes forming."""

    tf_upper = timeframe.upper()
    if SESSION and tf_upper.endswith("D"):
        localized = index.tz_convert(SESSION.close_timezone)
        shifted = localized + pd.DateOffset(days=1)
        normalized = shifted.normalize()
        offset = pd.Timedelta(
            hours=SESSION.close_time.hour,
            minutes=SESSION.close_time.minute,
            seconds=SESSION.close_time.second,
        )
        close_aligned = normalized + offset
        return close_aligned.tz_convert("UTC")

    return index.tz_convert("UTC")


def _compute_bar_windows(
    open_index: pd.DatetimeIndex,
    aligned_index: pd.DatetimeIndex,
    timeframe: str,
) -> pd.DataFrame:
    """Return per-bar open/close times keyed by available timestamp."""

    open_index = pd.DatetimeIndex(open_index)
    aligned_index = pd.DatetimeIndex(aligned_index)
    if open_index.tz is None:
        open_index = open_index.tz_localize("UTC")
    if aligned_index.tz is None:
        aligned_index = aligned_index.tz_localize("UTC")

    if len(open_index) != len(aligned_index):
        raise ValueError("Open/close indices must have matching lengths.")

    tf_lower = timeframe.lower()
    if tf_lower.endswith("d"):
        close_index = aligned_index
    else:
        delta = timeframe_to_timedelta(timeframe)
        close_index = open_index + delta

    return pd.DataFrame(
        {
            "bar_open": open_index.tz_convert("UTC"),
            "bar_close": close_index.tz_convert("UTC"),
        },
        index=aligned_index,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeframes",
        nargs="*",
        choices=list(TIMEFRAME_EXPORTS.keys()),
        help="Subset of timeframes to rebuild. Defaults to all.",
    )
    parser.add_argument(
        "--include-bar-windows",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Include *_bar_open and *_bar_close columns for each "
            "timeframe represented in the parquet. Use "
            "--no-include-bar-windows to disable."
        ),
    )
    return parser.parse_args()


def _build_embedded_frames(
    target_timeframes: list[str],
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, list[str]],
    dict[str, pd.DataFrame],
]:
    feature_frames: dict[str, pd.DataFrame] = {}
    bar_windows: dict[str, pd.DataFrame] = {}
    open_indices: dict[str, pd.DatetimeIndex] = {}
    for tf in target_timeframes:
        df = _load_export(TIMEFRAME_EXPORTS[tf][0])
        open_index = pd.DatetimeIndex(df.index)
        close_index = _align_available_index(open_index, tf)
        df.index = close_index
        feature_frames[tf] = df
        open_indices[tf] = open_index
        bar_windows[tf] = _compute_bar_windows(open_index, close_index, tf)

    td_minutes = {
        tf: timeframe_to_timedelta(tf).total_seconds() / 60 for tf in feature_frames
    }

    embedded: dict[str, pd.DataFrame] = {}
    dependencies: dict[str, list[str]] = {}
    ordered_targets = sorted(target_timeframes, key=lambda tf: td_minutes[tf])

    for base_tf in ordered_targets:
        base_index = feature_frames[base_tf].index
        base_df = feature_frames[base_tf].reindex(base_index)
        dependencies[base_tf] = [base_tf]

        for higher_tf in ordered_targets:
            if td_minutes[higher_tf] <= td_minutes[base_tf]:
                continue
            higher_df = feature_frames[higher_tf]
            aligned = higher_df.reindex(base_index, method="ffill")
            base_df = pd.concat([base_df, aligned], axis=1)
            dependencies[base_tf].append(higher_tf)

        embedded[base_tf] = base_df

    return embedded, dependencies, bar_windows


def _finalize_frame(
    df: pd.DataFrame,
    timeframes: list[str],
    include_windows: bool,
    bar_windows: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    final_df = df.reset_index()
    index_name = df.index.name or TIMESTAMP_COLUMN
    final_df = final_df.rename(columns={index_name: TIMESTAMP_COLUMN})
    final_df[TIMESTAMP_COLUMN] = pd.to_datetime(
        final_df[TIMESTAMP_COLUMN],
        utc=True,
    )
    cols = final_df.columns.tolist()
    ordered_cols = [TIMESTAMP_COLUMN] + [c for c in cols if c != TIMESTAMP_COLUMN]
    final_df = final_df[ordered_cols]

    if include_windows:
        final_df = _append_bar_windows(final_df, timeframes, bar_windows)
    return final_df


def _append_bar_windows(
    frame: pd.DataFrame,
    timeframes: list[str],
    bar_windows: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    available_idx = pd.DatetimeIndex(frame[TIMESTAMP_COLUMN])

    for tf in timeframes:
        windows = bar_windows[tf].reindex(available_idx, method="ffill")
        slug = tf.lower()
        open_col = f"{slug}_bar_open"
        close_col = f"{slug}_bar_close"
        open_values = windows["bar_open"].to_numpy()
        close_values = windows["bar_close"].to_numpy()
        frame[open_col] = open_values
        frame[close_col] = close_values

        mask = (~pd.isna(open_values)) & (~pd.isna(close_values))
        if mask.any() and np.any(close_values[mask] < open_values[mask]):
            raise ValueError(
                f"Look-ahead risk detected for timeframe {tf}; "
                "bar close precedes bar open."
            )

    return frame


def _prepare_output_dir() -> Path:
    cache_dir = PURE_GOLDEN_DIR
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _write_metadata(
    cache_dir: Path,
    frames: dict[str, pd.DataFrame],
    outputs: dict[str, Path],
) -> None:
    from datetime import datetime, timezone

    metadata: dict[str, object] = {
        "symbol": SYMBOL,
        "normalized_symbol": SYMBOL.replace("/", ""),
        "data_root": str(DATA_ROOT.resolve()),
        "config_path": str(CONFIG_PATH.resolve()),
        "config_hash": _config_hash(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": {},
    }

    timeframes_meta: dict[str, dict[str, object]] = {}
    metadata["timeframes"] = timeframes_meta

    for timeframe, df in frames.items():
        parquet_path = outputs[timeframe]
        stored_df = pd.read_parquet(parquet_path)
        timestamp_series = pd.to_datetime(stored_df[TIMESTAMP_COLUMN], utc=True)
        timeframes_meta[timeframe] = {
            "columns": stored_df.columns.tolist(),
            "rows": int(len(stored_df)),
            "start": timestamp_series.iloc[0].isoformat() if len(stored_df) else None,
            "end": timestamp_series.iloc[-1].isoformat() if len(stored_df) else None,
        }

    (cache_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))


def main() -> None:
    args = _parse_args()
    targets = args.timeframes or list(TIMEFRAME_EXPORTS.keys())
    embedded, dependencies, bar_windows = _build_embedded_frames(targets)
    cache_dir = _prepare_output_dir()
    written_paths: dict[str, Path] = {}

    for timeframe in targets:
        _, parquet_name = TIMEFRAME_EXPORTS[timeframe]
        df = embedded[timeframe]
        final_df = _finalize_frame(
            df,
            dependencies[timeframe],
            args.include_bar_windows,
            bar_windows,
        )
        filename = PARQUET_FILENAMES[timeframe]
        dest = cache_dir / filename
        final_df.to_parquet(dest, index=False)
        written_paths[timeframe] = dest
        print(
            f"Wrote {dest.relative_to(PROJECT_ROOT)} "
            f"({len(final_df)} rows, {len(final_df.columns)} columns)"
        )

    _write_metadata(cache_dir, embedded, written_paths)

    descriptor = build_global_feature_caches(
        symbol=SYMBOL,
        data_root=DATA_ROOT,
        cache_root=TEST_CACHE_ROOT,
        config_path=CONFIG_PATH,
        timeframes=targets,
        overwrite=True,
        include_bar_windows=True,
    )
    print(
        "Built builder cache at " f"{descriptor.base_dir().relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
