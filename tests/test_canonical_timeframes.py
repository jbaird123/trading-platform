from __future__ import annotations

import json
from pathlib import Path

from trading_platform.data.timeframe_aliases import canonicalize_column_name
from trading_platform.reporting.csv_export import _flatten_context_keys


def _metadata_paths() -> list[Path]:
    base_dir = Path("data") / "cache" / "global_features"
    if not base_dir.exists():
        return []
    paths: list[Path] = []
    for symbol_dir in base_dir.iterdir():
        if not symbol_dir.is_dir():
            continue
        for config_dir in symbol_dir.iterdir():
            metadata = config_dir / "metadata.json"
            if metadata.exists():
                paths.append(metadata)
    return paths


def test_cache_metadata_columns_are_canonical() -> None:
    for metadata_path in _metadata_paths():
        metadata = json.loads(metadata_path.read_text())
        timeframes = metadata.get("timeframes", {})
        for frame_meta in timeframes.values():
            cols = frame_meta.get("columns", [])
            for column in cols:
                normalized = canonicalize_column_name(column)
                assert normalized == column, (
                    f"{metadata_path} column {column!r} is not canonical "
                    f"(normalized to {normalized!r})"
                )


def test_context_keys_flatten_to_canonical_names() -> None:
    ctx = {"global_features": {"15min_ema_50": 0.9, "1h_rsi_14": 55.0}}
    keys = _flatten_context_keys(ctx)
    assert all(key.startswith("ctx_global_features_") for key in keys)
    assert "ctx_global_features_15min_ema_50" in keys
    assert "ctx_global_features_1h_rsi_14" in keys
