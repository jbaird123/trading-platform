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
from trading_platform.core.config import GlobalFeatureSetConfig
from trading_platform.core.global_features import (
    feature_to_dict,
    resolve_global_feature_manifest,
)
from trading_platform.core.utils import normalize_symbol
from trading_platform.data.bar_windows import compute_bar_window_columns
from trading_platform.data.handler import DataHandler
from trading_platform.data.instrument import InstrumentDefinition, SessionDefinition
from trading_platform.data.session_metadata import ALIGNED_TO_CLOSE_ATTR, SESSION_ATTR
from trading_platform.data.timeframe_aliases import (
    normalize_name_sequence,
    normalize_timeframe_columns,
)
from trading_platform.strategy.features import compute_features

logger = logging.getLogger(__name__)

_CACHE_SUBDIR = "features/cache"
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
        delta = pd.to_timedelta(timeframe)
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
        return (self.data_root / _CACHE_SUBDIR / slug).resolve()

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
    normalize_timeframe_labels: bool = False,
) -> GlobalFeatureCacheDescriptor:
    """
    Precompute global features for each execution timeframe.

    Returns:
        GlobalFeatureCacheDescriptor describing the cache location.
    """

    source_data_root = Path(data_root).resolve()
    storage_root = Path(cache_root).resolve() if cache_root else source_data_root
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

    handler = DataHandler(
        symbol=symbol,
        data_root=source_data_root,
        instrument=instrument,
    )
    resolved_instrument = instrument or getattr(handler, "instrument", None)
    default_session: SessionDefinition | None = None
    if resolved_instrument and resolved_instrument.sessions:
        default_session = resolved_instrument.sessions[0]

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
        aligned_flag = bool(df.attrs.get(ALIGNED_TO_CLOSE_ATTR, False))
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
        need_bar_windows = include_bar_windows or normalize_timeframe_labels
        bar_open: pd.DatetimeIndex | None = None
        bar_close: pd.DatetimeIndex | None = None
        bar_lookup: pd.DatetimeIndex | None = None
        if need_bar_windows:
            bar_open, bar_close, bar_lookup = _compute_bar_windows_for_cache(
                raw_index,
                timeframe,
                session,
            )

        if normalize_timeframe_labels:
            feature_df = normalize_timeframe_columns(feature_df)
            feature_columns = normalize_name_sequence(feature_columns)
            feature_df = feature_df.shift(1)

        aligned_index = _align_available_index(
            feature_df.index,
            timeframe,
            session,
            aligned_flag,
        )
        if normalize_timeframe_labels and bar_open is not None:
            aligned_index = bar_open

        timestamp_col = pd.Series(aligned_index, name="available_at")
        storage_df = feature_df.copy()
        storage_df.insert(0, "available_at", timestamp_col.to_numpy())
        storage_df["available_at"] = pd.to_datetime(
            storage_df["available_at"],
            utc=True,
        )

        tf_slug = timeframe.lower()
        extra_columns: list[str] = []
        if (
            include_bar_windows
            and bar_open is not None
            and bar_close is not None
            and bar_lookup is not None
        ):
            open_col = f"{tf_slug}_bar_open"
            close_col = f"{tf_slug}_bar_close"
            lookup_col = f"{tf_slug}_bar_lookup_key"
            storage_df[open_col] = bar_open.to_numpy()
            storage_df[close_col] = bar_close.to_numpy()
            storage_df[lookup_col] = bar_lookup.to_numpy()
            extra_columns.extend([open_col, close_col, lookup_col])

        tf_file = descriptor.timeframe_path(timeframe)
        storage_df.to_parquet(tf_file, index=False)

        stored_columns = ["available_at"] + feature_columns + extra_columns
        frame_meta: dict[str, object] = {
            "columns": stored_columns,
            "rows": int(len(feature_df)),
            "start": feature_df.index[0].isoformat() if len(feature_df) else None,
            "end": feature_df.index[-1].isoformat() if len(feature_df) else None,
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
        derived = [
            column
            for column in all_columns
            if column == feature_name or column.startswith(f"{feature_name}_")
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
    data_root: Path,
    config_path: Path,
    timeframe: str,
    feature_names: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, list[str]]] | None:
    """
    Load cached global features for the requested execution timeframe.
    """

    descriptor = _resolve_descriptor(symbol, data_root, config_path)
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
    cache_root: Path,
    config_path: Path,
    timeframe: str,
    feature_names: Sequence[str],
) -> bool:
    """Return True if the cache contains all requested feature columns."""

    descriptor = _resolve_descriptor(symbol, cache_root, config_path)
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
