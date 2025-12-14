"""Tests for manifest digest enforcement in the global features cache.

These tests verify that:
1. build_global_feature_cache writes a manifest_digest to metadata
2. load_cached_global_features raises ValueError when digest mismatch
3. Matching digests allow successful loading
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _write_sample_csv(path: Path) -> None:
    """Create a minimal CSV with OHLCV data."""
    idx = pd.date_range("2023-01-01", periods=720, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 100.0,
        }
    )
    df.to_csv(path, index=False)


def _write_sample_manifest(path: Path) -> None:
    """Create a minimal global features manifest."""
    path.write_text(
        "\n".join(
            [
                "features:",
                '  - name: "5min_test_ema"',  # Must have timeframe prefix
                '    type: "EMA"',
                '    params: {"length": 10}',
                '    timeframe: "5min"',
            ]
        )
    )


def test_build_global_feature_cache_writes_manifest_digest(tmp_path):
    """Test that build_global_feature_caches writes manifest_digest to metadata."""
    from trading_platform.core.global_features_cache import build_global_feature_caches

    # Setup
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)

    manifest_path = tmp_path / "manifest.yaml"
    _write_sample_manifest(manifest_path)

    cache_root = tmp_path / "cache"

    # Build the cache
    descriptor = build_global_feature_caches(
        symbol="EURUSD",
        data_root=data_root,
        config_path=manifest_path,
        timeframes=["5min"],
        overwrite=True,
        cache_root=cache_root,
    )

    # Read metadata
    metadata_path = descriptor.metadata_path()
    assert metadata_path.exists(), "Metadata file should exist"

    metadata = json.loads(metadata_path.read_text())

    # Verify manifest_digest is present (will be implemented in Task 5)
    # For now, this test will fail until Task 5 is implemented
    assert "manifest_digest" in metadata, "Metadata must include manifest_digest"
    assert isinstance(metadata["manifest_digest"], str)
    assert len(metadata["manifest_digest"]) == 64  # SHA256 hex digest


def test_load_cached_features_raises_on_digest_mismatch(tmp_path):
    """Test that loading cache with mismatched digest raises ValueError."""
    from trading_platform.core.global_features_cache import (
        build_global_feature_caches,
        load_cached_global_features,
    )

    # Setup and build initial cache
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    _write_sample_csv(csv_dir / "eurusd_1min.csv")

    manifest_path = tmp_path / "manifest.yaml"
    _write_sample_manifest(manifest_path)

    cache_root = tmp_path / "cache"
    descriptor = build_global_feature_caches(
        symbol="EURUSD",
        data_root=data_root,
        config_path=manifest_path,
        timeframes=["5min"],
        overwrite=True,
        cache_root=cache_root,
    )

    # Tamper with the metadata to simulate a digest mismatch
    # (In practice, this would happen if manifest file content changed
    # but file path stayed the same, which is prevented by config_hash)
    metadata_path = descriptor.metadata_path()
    metadata = json.loads(metadata_path.read_text())
    metadata["manifest_digest"] = "0" * 64  # Invalid digest
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Attempt to load with mismatched manifest should raise
    with pytest.raises(ValueError, match="[Mm]anifest.*digest"):
        load_cached_global_features(
            symbol="EURUSD",
            timeframe="5min",
            cache_root=cache_root,
            config_path=manifest_path,
            feature_names=["5min_test_ema"],  # Added required arg
            session_group="forex",
        )


def test_load_cached_features_error_message_includes_digests(tmp_path):
    """Test that digest mismatch error includes both expected and actual digests."""
    from trading_platform.core.global_features_cache import (
        build_global_feature_caches,
        load_cached_global_features,
    )

    # Setup
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    _write_sample_csv(csv_dir / "eurusd_1min.csv")

    manifest_path = tmp_path / "manifest.yaml"
    _write_sample_manifest(manifest_path)

    cache_root = tmp_path / "cache"
    descriptor = build_global_feature_caches(
        symbol="EURUSD",
        data_root=data_root,
        config_path=manifest_path,
        timeframes=["5min"],
        overwrite=True,
        cache_root=cache_root,
    )

    # Read the stored digest
    metadata_path = descriptor.metadata_path()
    metadata = json.loads(metadata_path.read_text())
    original_digest = metadata["manifest_digest"]

    # Tamper with the stored digest
    fake_digest = "0" * 64
    metadata["manifest_digest"] = fake_digest
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Error should include both digests
    with pytest.raises(ValueError) as exc_info:
        load_cached_global_features(
            symbol="EURUSD",
            timeframe="5min",
            cache_root=cache_root,
            config_path=manifest_path,
            feature_names=["5min_test_ema"],
            session_group="forex",
        )

    error_message = str(exc_info.value)
    # Should mention both the stored (fake) and current (original) digest
    assert fake_digest[:16] in error_message  # Stored digest
    assert original_digest[:16] in error_message or "current" in error_message.lower()


def test_load_cached_features_succeeds_with_matching_digest(tmp_path):
    """Test that loading cache with matching digest succeeds."""
    from trading_platform.core.global_features_cache import (
        build_global_feature_caches,
        load_cached_global_features,
    )

    # Setup
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    _write_sample_csv(csv_dir / "eurusd_1min.csv")

    manifest_path = tmp_path / "manifest.yaml"
    _write_sample_manifest(manifest_path)

    cache_root = tmp_path / "cache"
    _ = build_global_feature_caches(
        symbol="EURUSD",
        data_root=data_root,
        config_path=manifest_path,
        timeframes=["5min"],
        overwrite=True,
        cache_root=cache_root,
    )

    # Load with the same manifest should succeed
    result = load_cached_global_features(
        symbol="EURUSD",
        timeframe="5min",
        cache_root=cache_root,
        config_path=manifest_path,
        feature_names=["5min_test_ema"],  # Added required arg
        session_group="forex",
    )

    assert result is not None
    df, mapping = result
    assert isinstance(df, pd.DataFrame)
    assert "5min_test_ema" in df.columns
    assert "5min_test_ema" in mapping


def test_manifest_digest_is_deterministic(tmp_path):
    """Test that the same manifest always produces the same digest."""
    from trading_platform.core.global_features_cache import compute_manifest_digest

    manifest = {
        "features": [
            {
                "name": "ema_20",
                "type": "EMA",
                "params": {"length": 20},
                "timeframe": "5min",
            }
        ]
    }

    # Compute digest multiple times
    digest1 = compute_manifest_digest(manifest)
    digest2 = compute_manifest_digest(manifest)
    digest3 = compute_manifest_digest(manifest)

    assert digest1 == digest2 == digest3
    assert isinstance(digest1, str)
    assert len(digest1) == 64  # SHA256 hex


def test_manifest_digest_changes_with_content(tmp_path):
    """Test that different manifests produce different digests."""
    from trading_platform.core.global_features_cache import compute_manifest_digest

    manifest1 = {
        "features": [{"name": "ema_20", "type": "EMA", "params": {"length": 20}}]
    }

    manifest2 = {
        "features": [{"name": "ema_30", "type": "EMA", "params": {"length": 30}}]
    }

    digest1 = compute_manifest_digest(manifest1)
    digest2 = compute_manifest_digest(manifest2)

    assert digest1 != digest2


def test_manifest_digest_handles_transient_objects(tmp_path):
    """Test compute_manifest_digest handles non-JSON-serializable types."""
    import numpy as np
    from trading_platform.core.global_features_cache import compute_manifest_digest

    manifest_with_transients = {
        "features": [
            {
                "name": "ema_20",
                "type": "EMA",
                "params": {
                    "length": np.int64(20),  # numpy type
                    "timestamp": pd.Timestamp("2023-01-01"),  # pandas type
                },
            }
        ]
    }

    # Should handle conversion internally
    digest = compute_manifest_digest(manifest_with_transients)
    assert isinstance(digest, str)
    assert len(digest) == 64


def test_manifest_digest_normalizes_dict_order(tmp_path):
    """Test that dict key order doesn't affect digest."""
    from trading_platform.core.global_features_cache import compute_manifest_digest

    manifest1 = {
        "features": [
            {
                "name": "ema",
                "type": "EMA",
                "params": {"length": 20, "source": "close"},
            }
        ]
    }

    manifest2 = {
        "features": [
            {
                "name": "ema",
                "type": "EMA",
                "params": {"source": "close", "length": 20},  # Different order
            }
        ]
    }

    digest1 = compute_manifest_digest(manifest1)
    digest2 = compute_manifest_digest(manifest2)

    # Should be identical despite different dict ordering
    assert digest1 == digest2
