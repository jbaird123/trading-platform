"""Ensure on-the-fly global feature computation matches the cached builder."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml
from trading_platform.data.timeframe_aliases import normalize_timeframe_columns
from trading_platform.strategy.features import compute_features

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Use 15min timeframe where we have golden OHLCV and cache available
RAW_15M_CSV = (
    PROJECT_ROOT
    / "data"
    / "dvc"
    / "golden"
    / "ohlcv"
    / "trading_platform"
    / "full"
    / "eurusd"
    / "eurusd_15min.csv"
)
GLOBAL_FEATURES_CONFIG = (
    PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "global.yaml"
)
# Default cache produced by the cache builder
CACHE_15M_PARQUET = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "global_features"
    / "eurusd"
    / "bed9c0d739baefcc0a27cb4ad6896f502a7ad23579172579efa2be53c55f3874"
    / "15min.parquet"
)


@pytest.mark.parametrize("sample_size", [5])
def test_global_feature_cache_alignment(sample_size: int) -> None:
    """Recompute global features and ensure they match the cached values."""
    cache_df = pd.read_parquet(CACHE_15M_PARQUET)
    cache_df["available_at"] = pd.to_datetime(cache_df["available_at"])
    cache_df = cache_df.set_index("available_at").sort_index()

    raw_df = pd.read_csv(RAW_15M_CSV, parse_dates=["timestamp"])
    raw_df = raw_df.set_index("timestamp").sort_index()

    cfg = yaml.safe_load(GLOBAL_FEATURES_CONFIG.read_text())
    specs = cfg.get("features", [])
    computed = compute_features(raw_df, specs, None)
    computed = normalize_timeframe_columns(computed)
    computed["available_at"] = computed.index
    computed = computed.set_index("available_at").sort_index()

    # Pick a small slice where both datasets overlap and have no NaNs
    common_index = cache_df.index.intersection(computed.index)
    assert len(common_index) > sample_size
    sample_times = common_index[:sample_size]

    for ts in sample_times:
        cache_row = cache_df.loc[ts]
        computed_row = computed.loc[ts]
        common_cols = cache_row.index.intersection(computed_row.index)
        assert not common_cols.empty
        pd.testing.assert_series_equal(
            computed_row[common_cols],
            cache_row[common_cols],
            rtol=1e-6,
            atol=1e-8,
            check_names=False,
        )
