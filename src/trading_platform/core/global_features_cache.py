"""Caching utilities for precomputing global feature matrices."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from os import fspath
from pathlib import Path
from typing import Iterable, Sequence, cast

import pandas as pd
import yaml
from trading_platform.core import paths
from trading_platform.core.config import GlobalFeatureSetConfig
from trading_platform.core.global_features import (
    feature_to_dict,
    resolve_global_feature_manifest,
)
from trading_platform.core.utils import normalize_symbol
from trading_platform.data.bar_windows import compute_bar_window_columns
from trading_platform.data.handler import DataHandler
from trading_platform.data.instrument import InstrumentDefinition, SessionDefinition
from trading_platform.data.resample import timeframe_to_timedelta
from trading_platform.data.session_metadata import SESSION_ATTR
from trading_platform.data.timeframe_aliases import (
    normalize_name_sequence,
    normalize_timeframe_columns,
    normalize_timeframe_prefix,
)
from trading_platform.strategy.features import compute_features

logger = logging.getLogger(__name__)

_CACHE_SUBDIR = ""
_DEFAULT_TIMEFRAMES: tuple[str, ...] = ("5min", "15min", "1H", "4H", "1D")


def _hash_file(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _sorted_unique_timeframes(timeframes: Iterable[str]) -> list[str]:
    unique = {tf for tf in timeframes if tf}
    if not unique:
        return []
    return sorted(unique, key=lambda tf: _timeframe_sort_key(tf))


def _timeframe_sort_key(timeframe: str) -> tuple[int, str]:
    try:
        delta = pd.to_timedelta(timeframe.lower())
        minutes = int(delta.total_seconds() // 60)
    except Exception:  # pragma: no cover - relies on pandas parsing
        minutes = 0
    return (minutes, timeframe.lower())


def _align_available_index(
    index: pd.Index,
    timeframe: str,
    session: SessionDefinition | None,
    aligned_to_close: bool,
) -> pd.DatetimeIndex:
    """Return timestamps that reflect when bar-level data is usable."""

    if not isinstance(index, pd.DatetimeIndex):
        index = pd.DatetimeIndex(index)

    tf_lower = timeframe.lower()
    if session and tf_lower.endswith("d"):
        localized = index.tz_convert(session.close_timezone)
        normalized = localized.normalize()
        offset = pd.Timedelta(
            hours=session.close_time.hour,
            minutes=session.close_time.minute,
            seconds=session.close_time.second,
        )
        close_aligned = normalized + offset
        return close_aligned.tz_convert("UTC")

    if aligned_to_close:
        return index.tz_convert("UTC")

    return index.tz_convert("UTC")


def _compute_bar_windows_for_cache(
    raw_index: pd.Index,
    timeframe: str,
    session: SessionDefinition | None,
) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]:
    """Return bar open/close timestamps for cached rows."""

    return compute_bar_window_columns(raw_index, timeframe, session)


def _build_timeframe_dependencies(timeframes: Sequence[str]) -> dict[str, list[str]]:
    minutes = {tf: timeframe_to_timedelta(tf).total_seconds() / 60 for tf in timeframes}
    ordered = sorted(timeframes, key=lambda tf: minutes[tf])
    dependencies: dict[str, list[str]] = {}
    for base_tf in ordered:
        deps = [tf for tf in ordered if minutes[tf] >= minutes[base_tf]]
        dependencies[base_tf] = deps
    return dependencies


def _merge_timeframes_for_output(
    base_timeframe: str,
    dependencies: dict[str, list[str]],
    raw_frames: dict[str, pd.DataFrame],
    include_bar_windows: bool,
) -> pd.DataFrame:
    base_raw = raw_frames[base_timeframe]
    base_result = pd.DataFrame(
        {"available_at": pd.to_datetime(base_raw["bar_open"], utc=True)}
    )
    base_result = base_result.sort_values("available_at").reset_index(drop=True)
    concatenated_parts: list[pd.DataFrame] = [base_result]

    for timeframe in dependencies.get(base_timeframe, []):
        frame = raw_frames[timeframe]
        merged = pd.merge_asof(
            base_result[["available_at"]],
            frame,
            left_on="available_at",
            right_on="bar_close",
            direction="backward",
            allow_exact_matches=True,
        )
        slug = timeframe.lower()
        feature_cols = [
            col
            for col in frame.columns
            if col not in {"bar_open", "bar_close", "bar_lookup"}
        ]
        if feature_cols:
            concatenated_parts.append(merged[feature_cols].copy())

        if include_bar_windows:
            bar_windows = pd.DataFrame(
                {
                    f"{slug}_bar_open": merged["bar_open"],
                    f"{slug}_bar_close": merged["bar_close"],
                    f"{slug}_bar_lookup_key": merged["bar_lookup"],
                }
            )
            concatenated_parts.append(bar_windows)

    result = pd.concat(concatenated_parts, axis=1)
    result = result.loc[:, ~result.columns.duplicated(keep="last")]

    cols = result.columns.tolist()
    ordered_cols = ["available_at"] + [c for c in cols if c != "available_at"]
    return result[ordered_cols]


def derive_execution_timeframes(config_path: Path) -> list[str]:
    """
    Inspect a global features manifest and return sorted execution timeframes.
    """

    try:
        data = yaml.safe_load(config_path.read_text())
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - malformed YAML
        raise ValueError(
            f"Failed to parse global features config at {config_path}"
        ) from exc

    config = GlobalFeatureSetConfig.model_validate(data)
    declared = [feature.timeframe for feature in config.features if feature.timeframe]
    if not declared:
        return list(_DEFAULT_TIMEFRAMES)
    return _sorted_unique_timeframes(declared)


@dataclass(frozen=True)
class GlobalFeatureCacheDescriptor:
    """Location and metadata for a cached global feature set."""

    symbol: str
    data_root: Path
    config_path: Path
    config_hash: str

    def base_dir(self) -> Path:
        slug = normalize_symbol(self.symbol).lower()
        base = self.data_root
        if _CACHE_SUBDIR:
            base = base / _CACHE_SUBDIR
        return (base / slug / self.config_hash).resolve()

    def timeframe_path(self, timeframe: str) -> Path:
        tf_slug = timeframe.lower().replace("/", "_")
        return self.base_dir() / f"{tf_slug}.parquet"

    def metadata_path(self) -> Path:
        return self.base_dir() / "metadata.json"


def _resolve_descriptor(
    symbol: str,
    data_root: Path,
    config_path: Path,
) -> GlobalFeatureCacheDescriptor:
    data_root = Path(data_root).resolve()
    config_path = Path(config_path).resolve()
    config_hash = _hash_file(config_path)
    return GlobalFeatureCacheDescriptor(symbol, data_root, config_path, config_hash)


def build_global_feature_caches(
    *,
    symbol: str,
    data_root: Path,
    config_path: Path,
    timeframes: Sequence[str] | None = None,
    overwrite: bool = False,
    instrument: InstrumentDefinition | None = None,
    cache_root: Path | None = None,
    include_bar_windows: bool = False,
) -> GlobalFeatureCacheDescriptor:
    """
    Precompute global features for each execution timeframe.

    Returns:
        GlobalFeatureCacheDescriptor describing the cache location.
    """

    source_data_root = Path(data_root).resolve()
    storage_root = (
        Path(cache_root).expanduser().resolve()
        if cache_root
        else paths.GLOBAL_FEATURE_CACHE_DIR
    )
    descriptor = _resolve_descriptor(symbol, storage_root, config_path)
    cache_dir = descriptor.base_dir()

    if cache_dir.exists():
        if overwrite:
            shutil.rmtree(cache_dir)
        else:
            logger.info(
                "Global feature cache already exists at %s; reuse it or "
                "pass overwrite=True to rebuild.",
                cache_dir,
            )
            return descriptor

    cache_dir.mkdir(parents=True, exist_ok=True)

    tf_list = (
        list(timeframes) if timeframes else derive_execution_timeframes(config_path)
    )
    if not tf_list:
        tf_list = list(_DEFAULT_TIMEFRAMES)

    timeframes_meta: dict[str, dict[str, object]] = {}
    metadata: dict[str, object] = {
        "symbol": symbol,
        "normalized_symbol": normalize_symbol(symbol),
        "data_root": fspath(source_data_root),
        "cache_root": fspath(descriptor.data_root),
        "config_path": fspath(descriptor.config_path),
        "config_hash": descriptor.config_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": timeframes_meta,
    }

    handler = DataHandler(
        symbol=symbol,
        data_root=source_data_root,
        instrument=instrument,
    )
    resolved_instrument = instrument or getattr(handler, "instrument", None)
    default_session: SessionDefinition | None = None
    if resolved_instrument and resolved_instrument.sessions:
        default_session = resolved_instrument.sessions[0]

    raw_frames: dict[str, pd.DataFrame] = {}

    for timeframe in tf_list:
        resolved_path, resolved_features = resolve_global_feature_manifest(
            timeframe, descriptor.config_path, warn_on_default=False
        )
        if not resolved_features:
            logger.warning(
                "No global features resolved for timeframe %s (config %s).",
                timeframe,
                resolved_path,
            )
            continue

        df = handler.get_data(timeframe=timeframe)
        raw_index = pd.DatetimeIndex(df.index)
        session = df.attrs.get(SESSION_ATTR) or default_session
        base_columns = list(df.columns)
        specs = [feature_to_dict(feature) for feature in resolved_features]
        enriched = compute_features(df, specs, strategy_parameters={})
        feature_columns = [col for col in enriched.columns if col not in base_columns]
        if not feature_columns:
            logger.warning(
                "Resolved features for timeframe %s produced no columns.",
                timeframe,
            )
            continue

        feature_df = enriched[feature_columns].copy()
        feature_df.attrs.pop(SESSION_ATTR, None)
        bar_open, bar_close, bar_lookup = _compute_bar_windows_for_cache(
            raw_index,
            timeframe,
            session,
        )

        feature_df = normalize_timeframe_columns(feature_df)
        feature_columns = normalize_name_sequence(feature_columns)

        # Convert bar_lookup to ISO string format (matching TradingView golden cache)
        bar_lookup_strings = pd.Series(
            [
                ts.isoformat().replace("+00:00", "Z") if pd.notna(ts) else None
                for ts in bar_lookup
            ]
        )

        aligned_index = bar_open

        timestamp_col = pd.Series(aligned_index, name="available_at")
        storage_df = feature_df.copy()
        storage_df.insert(0, "available_at", timestamp_col.to_numpy())
        storage_df["available_at"] = pd.to_datetime(
            storage_df["available_at"],
            utc=True,
        )

        raw_frame = feature_df.copy()
        raw_frame["bar_open"] = bar_open.to_numpy()
        raw_frame["bar_close"] = bar_close.to_numpy()
        raw_frame["bar_lookup"] = bar_lookup_strings.to_numpy()
        raw_frame = raw_frame.sort_values("bar_close").reset_index(drop=True)
        raw_frames[timeframe] = raw_frame

    if not raw_frames:
        raise RuntimeError("No valid frames were produced; check config inputs.")

    dependencies = _build_timeframe_dependencies(tf_list)

    for timeframe in tf_list:
        output_frame = _merge_timeframes_for_output(
            timeframe,
            dependencies,
            raw_frames,
            include_bar_windows=include_bar_windows,
        )

        tf_file = descriptor.timeframe_path(timeframe)
        output_frame.to_parquet(tf_file, index=False)

        timestamp_series = pd.to_datetime(output_frame["available_at"], utc=True)
        frame_meta: dict[str, object] = {
            "columns": output_frame.columns.tolist(),
            "rows": int(len(output_frame)),
            "start": (
                timestamp_series.iloc[0].isoformat() if len(output_frame) else None
            ),
            "end": (
                timestamp_series.iloc[-1].isoformat() if len(output_frame) else None
            ),
        }
        timeframes_meta[timeframe] = frame_meta
        logger.info("Cached %s global features at %s", timeframe, tf_file)

    if not timeframes_meta:
        raise RuntimeError(
            "Global feature cache build produced no files. Verify "
            "timeframes and config inputs."
        )

    descriptor.metadata_path().write_text(json.dumps(metadata, indent=2))
    return descriptor


def _load_metadata(descriptor: GlobalFeatureCacheDescriptor) -> dict[str, object]:
    metadata_path = descriptor.metadata_path()
    if not metadata_path.exists():
        return {}
    try:
        raw = json.loads(metadata_path.read_text())
    except json.JSONDecodeError:  # pragma: no cover - unexpected corruption
        return {}
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    return {}


def _columns_for_features(
    all_columns: list[str],
    feature_names: Sequence[str],
) -> tuple[list[str], dict[str, list[str]]]:
    selected: list[str] = []
    mapping: dict[str, list[str]] = {}
    for feature_name in feature_names:
        if not feature_name:
            continue
        canonical_name = normalize_timeframe_prefix(feature_name)
        derived = [
            column
            for column in all_columns
            if column == canonical_name or column.startswith(f"{canonical_name}_")
        ]
        if derived:
            mapping[feature_name] = derived
            for column in derived:
                if column not in selected:
                    selected.append(column)
    return selected, mapping


def load_cached_global_features(
    *,
    symbol: str,
    cache_root: Path | None = None,
    config_path: Path,
    timeframe: str,
    feature_names: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, list[str]]] | None:
    """
    Load cached global features for the requested execution timeframe.
    """

    storage_root = (
        Path(cache_root).expanduser().resolve()
        if cache_root
        else paths.GLOBAL_FEATURE_CACHE_DIR
    )
    descriptor = _resolve_descriptor(symbol, storage_root, config_path)
    metadata = _load_metadata(descriptor)
    frame_meta: dict[str, object] | None = None
    timeframes_obj = metadata.get("timeframes") if metadata else None
    if isinstance(timeframes_obj, dict):
        candidate = timeframes_obj.get(timeframe)
        if isinstance(candidate, dict):
            frame_meta = candidate
    if frame_meta is None:
        return None

    tf_path = descriptor.timeframe_path(timeframe)
    if not tf_path.exists():
        return None

    columns_obj = frame_meta.get("columns")
    all_columns = (
        [str(col) for col in columns_obj if isinstance(col, str)]
        if isinstance(columns_obj, list)
        else []
    )
    columns, mapping = _columns_for_features(all_columns, feature_names)
    if not columns:
        return None

    timestamp_col = "available_at"
    read_columns = columns.copy()
    if timestamp_col not in read_columns and timestamp_col in all_columns:
        read_columns = [timestamp_col] + read_columns

    df = pd.read_parquet(tf_path, columns=read_columns)
    if timestamp_col in df.columns:
        timestamps = pd.to_datetime(df[timestamp_col], utc=True)
        df = df.drop(columns=[timestamp_col]).set_index(timestamps)
    return df, mapping


def cache_covers_features(
    *,
    symbol: str,
    cache_root: Path | None = None,
    config_path: Path,
    timeframe: str,
    feature_names: Sequence[str],
) -> bool:
    """Return True if the cache contains all requested feature columns."""

    storage_root = (
        Path(cache_root).expanduser().resolve()
        if cache_root
        else paths.GLOBAL_FEATURE_CACHE_DIR
    )
    descriptor = _resolve_descriptor(symbol, storage_root, config_path)
    tf_path = descriptor.timeframe_path(timeframe)
    if not tf_path.exists():
        return False

    metadata = _load_metadata(descriptor)
    frame_meta: dict[str, object] | None = None
    timeframes_obj = metadata.get("timeframes") if metadata else None
    if isinstance(timeframes_obj, dict):
        candidate = timeframes_obj.get(timeframe)
        if isinstance(candidate, dict):
            frame_meta = candidate
    if frame_meta is None:
        return False

    columns_obj = frame_meta.get("columns")
    all_columns = (
        [str(col) for col in columns_obj if isinstance(col, str)]
        if isinstance(columns_obj, list)
        else []
    )
    _, mapping = _columns_for_features(all_columns, feature_names)
    required = {name for name in feature_names if name}
    return bool(required) and required.issubset(mapping.keys())
