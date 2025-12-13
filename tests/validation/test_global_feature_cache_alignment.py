"""Ensure on-the-fly global feature computation matches the cached builder."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from trading_platform.core.global_features import (
    feature_to_dict,
    resolve_global_feature_manifest,
)
from trading_platform.data.handler import DataHandler
from trading_platform.data.instrument import get_instrument_definition
from trading_platform.data.timeframe_aliases import normalize_timeframe_columns
from trading_platform.strategy.features import compute_features

PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_ROOT = PROJECT_ROOT / "data" / "cache_test" / "eurusd"


def _load_cache_dir() -> Path:
    """Locate the single cache directory under cache_test/eurusd."""
    candidates = [p for p in CACHE_ROOT.iterdir() if p.is_dir()]
    if not candidates:
        pytest.skip(f"No cache directories found under {CACHE_ROOT}")
    # If multiple exist, pick the one with metadata.json present
    for candidate in candidates:
        if (candidate / "metadata.json").exists():
            return candidate
    return candidates[0]


@pytest.mark.parametrize("timeframe", ["5min", "15min"])
def test_global_feature_cache_alignment(timeframe: str) -> None:
    """Recompute global features from raw data and compare to cached values."""
    cache_dir = _load_cache_dir()
    metadata_path = cache_dir / "metadata.json"
    if not metadata_path.exists():
        pytest.skip(f"Cache metadata not found: {metadata_path}")

    metadata = json.loads(metadata_path.read_text())
    config_path = Path(metadata["config_path"])
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    data_root = Path(metadata["data_root"])
    if not data_root.is_absolute():
        data_root = PROJECT_ROOT / data_root

    cache_path = cache_dir / f"{timeframe.lower()}.parquet"
    cache_df = pd.read_parquet(cache_path)
    cache_df["available_at"] = pd.to_datetime(cache_df["available_at"], utc=True)
    cache_df = cache_df.set_index("available_at").sort_index()

    instrument = get_instrument_definition("EURUSD")
    handler = DataHandler(
        symbol="EURUSD",
        data_root=data_root,
        instrument=instrument,
    )
    market_data = handler.get_data(timeframe=timeframe)
    market_data = market_data.sort_index()

    # Match the cache builder's start window to avoid EMA warmup drift
    cache_start = cache_df.index.min()
    market_data = market_data[market_data.index >= cache_start]

    # Resolve features for this timeframe
    _, resolved_features = resolve_global_feature_manifest(
        execution_timeframe=timeframe,
        config_path=config_path,
        warn_on_default=False,
    )
    specs = [feature_to_dict(f) for f in resolved_features]

    computed = compute_features(market_data, specs, None)
    computed = normalize_timeframe_columns(computed)
    computed["available_at"] = computed.index
    computed = computed.set_index("available_at").sort_index()

    # Use overlapping timestamps where computed data is non-NaN
    common_index = cache_df.index.intersection(computed.index)
    computed_common = computed.loc[common_index]
    computed_common = computed_common.dropna(axis=0, how="any")
    cache_common = cache_df.loc[computed_common.index]

    assert len(computed_common) > 0

    common_cols = cache_common.columns.intersection(computed_common.columns)
    assert not common_cols.empty

    # Compare a small sample to avoid huge memory use
    sample = computed_common.iloc[:5][common_cols]
    cache_sample = cache_common.iloc[:5][common_cols]
    pd.testing.assert_frame_equal(
        sample,
        cache_sample,
        rtol=1e-6,
        atol=1e-8,
        check_names=False,
    )
