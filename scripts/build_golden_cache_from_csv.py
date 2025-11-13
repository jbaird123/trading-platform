#!/usr/bin/env python3
"""
Build multi-timeframe golden feature caches directly from CSV exports.

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

import pandas as pd
from trading_platform.data.bar_windows import compute_bar_window_columns
from trading_platform.data.instrument import get_instrument_definition
from trading_platform.data.resample import timeframe_to_timedelta
from trading_platform.data.timeframe_aliases import normalize_timeframe_columns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
CONFIG_PATH = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "global.yaml"
SYMBOL = "EUR/USD"
SYMBOL_SLUG = "eurusd"

PURE_GOLDEN_DIR = (
    PROJECT_ROOT
    / "data"
    / "dvc"
    / "golden"
    / "features"
    / "trading_platform"
    / "cache"
    / SYMBOL_SLUG
)
# Filter trading platform cache to start at this date to limit downstream data size
GOLDEN_CACHE_START_DATE = pd.Timestamp("2020-03-01 22:00:00", tz="UTC")

TEST_CACHE_ROOT = PROJECT_ROOT / "data" / "dvc" / "golden"
TIMESTAMP_COLUMN = "available_at"
INSTRUMENT = get_instrument_definition(SYMBOL)
SESSION = INSTRUMENT.sessions[0] if INSTRUMENT.sessions else None

OHLC_COLUMNS = ["open", "high", "low", "close", "volume"]

TIMEFRAME_EXPORTS = OrderedDict(
    [
        (
            "15min",
            (
                "eurusd_15min_trading_platform.csv",
                "eurusd_15min_available_after_close.parquet",
            ),
        ),
        (
            "1H",
            (
                "eurusd_1h_trading_platform.csv",
                "eurusd_1h_available_after_close.parquet",
            ),
        ),
        (
            "4H",
            (
                "eurusd_4h_trading_platform.csv",
                "eurusd_4h_available_after_close.parquet",
            ),
        ),
        (
            "1D",
            (
                "eurusd_1d_trading_platform.csv",
                "eurusd_1d_available_after_close.parquet",
            ),
        ),
    ]
)
PARQUET_FILENAMES = {
    "15min": "15min.parquet",
    "1H": "1h.parquet",
    "4H": "4h.parquet",
    "1D": "1d.parquet",
}
COLUMN_RENAMES = {
    "m15_adx_14_DI+": "m15_adx_14_DIplus",
    "m15_adx_14_DI-": "m15_adx_14_DIminus",
    "h1_adx_14_DI+": "h1_adx_14_DIplus",
    "h1_adx_14_DI-": "h1_adx_14_DIminus",
    "h4_adx_14_DI+": "h4_adx_14_DIplus",
    "h4_adx_14_DI-": "h4_adx_14_DIminus",
    "d1_adx_14_DI+": "d1_adx_14_DIplus",
    "d1_adx_14_DI-": "d1_adx_14_DIminus",
}


def _config_hash() -> str:
    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()


def _format_lookup_strings(index: pd.DatetimeIndex) -> pd.Series:
    """Return ISO-8601 strings with Z suffix for each timestamp (or None)."""
    return pd.Series(
        [
            ts.isoformat().replace("+00:00", "Z") if pd.notna(ts) else None
            for ts in index
        ],
        index=index,
        dtype="object",
    )


def _load_export(csv_name: str) -> pd.DataFrame:
    path = RAW_DIR / csv_name
    if not path.exists():
        raise FileNotFoundError(f"Export not found: {path}")
    raw = pd.read_csv(path)

    # Handle either 'time' or 'timestamp' columns from legacy exports
    time_col = "time" if "time" in raw.columns else "timestamp"
    if time_col not in raw.columns:
        raise ValueError(f"Neither 'time' nor 'timestamp' column found in {path}")

    idx = pd.DatetimeIndex(pd.to_datetime(raw[time_col], utc=True), name="time")
    raw["_lookup_key"] = _format_lookup_strings(idx).to_numpy()
    df = (
        raw.drop(columns=[time_col])
        .set_index(idx)
        .sort_index()
        .drop(columns=OHLC_COLUMNS + ["timestamp"], errors="ignore")
    )
    df = df.rename(columns=COLUMN_RENAMES)
    df = normalize_timeframe_columns(df)

    # Filter to start at configured date
    if GOLDEN_CACHE_START_DATE is not None:
        df = df[df.index >= GOLDEN_CACHE_START_DATE]

    return df


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


def _load_timeframe_frame(timeframe: str) -> pd.DataFrame:
    """Load raw timeframe data and annotate open/close/lookup metadata."""

    raw_df = _load_export(TIMEFRAME_EXPORTS[timeframe][0]).rename(
        columns=COLUMN_RENAMES
    )
    raw_df = raw_df.sort_index()
    lookup_strings = raw_df.pop("_lookup_key")
    bar_open, bar_close, _ = compute_bar_window_columns(
        raw_df.index,
        timeframe,
        SESSION,
    )

    frame = raw_df.copy()
    frame["bar_open"] = bar_open
    frame["bar_close"] = bar_close
    frame["bar_lookup"] = lookup_strings
    frame = frame.sort_values("bar_close").reset_index(drop=True)
    return frame


def _build_dependencies(timeframes: list[str]) -> dict[str, list[str]]:
    """Map each base timeframe to the list of timeframes it depends on."""

    td_minutes = {
        tf: timeframe_to_timedelta(tf).total_seconds() / 60 for tf in timeframes
    }
    ordered = sorted(timeframes, key=lambda tf: td_minutes[tf])
    dependencies: dict[str, list[str]] = {}

    for base_tf in ordered:
        deps = [tf for tf in ordered if td_minutes[tf] >= td_minutes[base_tf]]
        dependencies[base_tf] = deps

    return dependencies


def _merge_features_for_timeframe(
    available_times: pd.Series,
    raw_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Return the latest raw bar whose close is <= available_at."""

    merged = pd.merge_asof(
        available_times.to_frame(name="available_at"),
        raw_frame,
        left_on="available_at",
        right_on="bar_close",
        direction="backward",
        allow_exact_matches=True,
    )
    return merged


def _build_target_frame(
    base_timeframe: str,
    dependencies: list[str],
    raw_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Construct the golden rows for a single target timeframe."""

    base_raw = raw_frames[base_timeframe]
    result = pd.DataFrame({"available_at": base_raw["bar_open"]})
    result = result.sort_values("available_at").reset_index(drop=True)

    for tf in dependencies:
        raw_frame = raw_frames[tf]
        merged = _merge_features_for_timeframe(result["available_at"], raw_frame)
        slug = tf.lower()

        feature_cols = [
            col
            for col in raw_frame.columns
            if col not in {"bar_open", "bar_close", "bar_lookup"}
        ]
        for col in feature_cols:
            result[col] = merged[col]

        result[f"{slug}_bar_open"] = merged["bar_open"]
        result[f"{slug}_bar_close"] = merged["bar_close"]
        result[f"{slug}_bar_lookup_key"] = merged["bar_lookup"]

    return result


def _validate_bar_windows(frame: pd.DataFrame, timeframes: list[str]) -> None:
    available = pd.to_datetime(frame[TIMESTAMP_COLUMN], utc=True)
    for tf in timeframes:
        slug = tf.lower()
        open_col = f"{slug}_bar_open"
        close_col = f"{slug}_bar_close"
        if open_col not in frame or close_col not in frame:
            continue
        opens = pd.to_datetime(frame[open_col], utc=True, errors="coerce")
        closes = pd.to_datetime(frame[close_col], utc=True, errors="coerce")
        mask = opens.notna() & closes.notna()
        if not mask.any():
            continue
        if (closes[mask] <= opens[mask]).any():
            raise ValueError(
                f"{tf} bar_close must be greater than bar_open for all rows."
            )
        if (closes[mask] > available[mask]).any():
            raise ValueError(
                f"{tf} bar_close exceeds available_at, indicating look-ahead bias."
            )


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
    raw_frames = {tf: _load_timeframe_frame(tf) for tf in TIMEFRAME_EXPORTS}
    dependencies = _build_dependencies(list(TIMEFRAME_EXPORTS.keys()))
    built_frames: dict[str, pd.DataFrame] = {}
    cache_dir = _prepare_output_dir()
    written_paths: dict[str, Path] = {}

    for timeframe in targets:
        _, parquet_name = TIMEFRAME_EXPORTS[timeframe]
        frame = _build_target_frame(
            timeframe,
            dependencies[timeframe],
            raw_frames,
        )
        frame["available_at"] = pd.to_datetime(
            frame["available_at"],
            utc=True,
        )
        _validate_bar_windows(frame, dependencies[timeframe])

        if not args.include_bar_windows:
            drop_cols = [
                col
                for col in frame.columns
                if col.endswith("_bar_open")
                or col.endswith("_bar_close")
                or col.endswith("_bar_lookup_key")
            ]
            frame = frame.drop(columns=drop_cols)

        cols = frame.columns.tolist()
        ordered_cols = [TIMESTAMP_COLUMN] + [c for c in cols if c != TIMESTAMP_COLUMN]
        frame = frame[ordered_cols]
        built_frames[timeframe] = frame

        filename = PARQUET_FILENAMES[timeframe]
        dest = cache_dir / filename
        frame.to_parquet(dest, index=False)
        written_paths[timeframe] = dest
        print(
            f"Wrote {dest.relative_to(PROJECT_ROOT)} "
            f"({len(frame)} rows, {len(frame.columns)} columns)"
        )

    _write_metadata(cache_dir, built_frames, written_paths)

    print("Golden cache rebuilt.")


if __name__ == "__main__":
    main()
