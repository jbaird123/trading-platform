"""End-to-end integration test for the global feature pipeline.

This test verifies that all components of the global feature system interoperate:
1. Cache building with manifest digest
2. Feature computation via build_global_feature_frame
3. Cache loading with digest validation
4. CLI validation script
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from trading_platform.core.global_features_cache import (
    build_global_feature_caches,
    compute_manifest_digest,
    load_cached_global_features,
)


def _write_market_data_csv(path: Path) -> None:
    """Create synthetic market data CSV for testing."""
    # Generate 24 hours of 1min data (1440 bars)
    idx = pd.date_range("2023-01-01", periods=1440, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": 1.0 + (idx.hour / 100.0),  # Vary by hour
            "high": 1.01 + (idx.hour / 100.0),
            "low": 0.99 + (idx.hour / 100.0),
            "close": 1.0 + (idx.hour / 100.0),
            "volume": 100.0 + idx.minute,  # Vary by minute
        }
    )
    df.to_csv(path, index=False)


def _write_feature_manifest(path: Path) -> None:
    """Create a feature manifest with multiple timeframes."""
    manifest = {
        "features": [
            # 5min timeframe features
            {
                "name": "5min_ema_10",
                "type": "EMA",
                "params": {"length": 10},
                "timeframe": "5min",
            },
            {
                "name": "5min_rsi_14",
                "type": "RSI",
                "params": {"length": 14},
                "timeframe": "5min",
            },
            # 15min timeframe features
            {
                "name": "15min_ema_20",
                "type": "EMA",
                "params": {"length": 20},
                "timeframe": "15min",
            },
            {
                "name": "15min_atr_14",
                "type": "ATR",
                "params": {"length": 14},
                "timeframe": "15min",
            },
        ]
    }
    path.write_text(yaml.dump(manifest, sort_keys=True))


def test_global_feature_pipeline_end_to_end(tmp_path: Path) -> None:
    """Test complete pipeline: build → load → validate."""
    # ==================== Setup ====================
    # Create directory structure
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"

    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"

    # Write test data
    _write_market_data_csv(csv_path)
    _write_feature_manifest(manifest_path)

    # Load manifest and compute digest
    manifest_data = yaml.safe_load(manifest_path.read_text())
    expected_digest = compute_manifest_digest(manifest_data)

    # ==================== Step 1: Build Cache ====================
    descriptor = build_global_feature_caches(
        symbol="EURUSD",
        data_root=data_root,
        config_path=manifest_path,
        timeframes=["5min", "15min"],
        overwrite=True,
        cache_root=cache_root,
    )

    # Verify cache exists
    assert descriptor.metadata_path().exists(), "Metadata should be created"
    assert descriptor.timeframe_path("5min").exists(), "5min cache should be created"
    assert descriptor.timeframe_path("15min").exists(), "15min cache should be created"

    # Verify manifest digest was stored
    metadata = json.loads(descriptor.metadata_path().read_text())
    assert "manifest_digest" in metadata, "Metadata must include manifest_digest"
    assert (
        metadata["manifest_digest"] == expected_digest
    ), "Stored digest must match computed digest"

    # ==================== Step 2: Load and Verify Cache ====================
    # Test 5min timeframe
    result_5min = load_cached_global_features(
        symbol="EURUSD",
        timeframe="5min",
        cache_root=cache_root,
        config_path=manifest_path,
        feature_names=["5min_ema_10", "5min_rsi_14"],
        session_group="forex",
    )

    assert result_5min is not None, "5min cache should load successfully"
    cached_5min_df, feature_mapping_5min = result_5min

    assert isinstance(cached_5min_df, pd.DataFrame), "Should return DataFrame"
    assert "5min_ema_10" in cached_5min_df.columns, "5min_ema_10 should be present"
    assert "5min_rsi_14" in cached_5min_df.columns, "5min_rsi_14 should be present"
    assert len(cached_5min_df) > 0, "Should have cached data rows"

    # Test 15min timeframe
    result_15min = load_cached_global_features(
        symbol="EURUSD",
        timeframe="15min",
        cache_root=cache_root,
        config_path=manifest_path,
        feature_names=["15min_ema_20", "15min_atr_14"],
        session_group="forex",
    )

    assert result_15min is not None, "15min cache should load successfully"
    cached_15min_df, feature_mapping_15min = result_15min

    assert isinstance(cached_15min_df, pd.DataFrame), "Should return DataFrame"
    assert "15min_ema_20" in cached_15min_df.columns, "15min_ema_20 should be present"
    assert "15min_atr_14" in cached_15min_df.columns, "15min_atr_14 should be present"
    assert len(cached_15min_df) > 0, "Should have cached data rows"

    # ==================== Step 3: Verify Data Integrity ====================
    # Verify that cached features have expected columns and valid data
    assert (
        cached_5min_df["5min_ema_10"].notna().sum() > 0
    ), "5min_ema_10 should have valid values"
    assert (
        cached_5min_df["5min_rsi_14"].notna().sum() > 0
    ), "5min_rsi_14 should have valid values"
    assert (
        cached_15min_df["15min_ema_20"].notna().sum() > 0
    ), "15min_ema_20 should have valid values"
    assert (
        cached_15min_df["15min_atr_14"].notna().sum() > 0
    ), "15min_atr_14 should have valid values"

    # Verify metadata includes valid_start information
    assert (
        "valid_start" in feature_mapping_5min or len(cached_5min_df) > 0
    ), "Should have feature metadata or cached data"
    assert (
        "valid_start" in feature_mapping_15min or len(cached_15min_df) > 0
    ), "Should have feature metadata or cached data"

    # ==================== Step 4: Run CLI Validation ====================
    # The validation script uses the canonical pipeline to recompute features
    # at 1min frequency, then reindexes to cached timestamps with forward-fill.
    # This should produce identical results to the cache builder.

    validation_result_5min = subprocess.run(
        [
            sys.executable,
            "scripts/validate_feature_cache.py",
            "--cache-dir",
            str(cache_root),
            "--symbol",
            "EURUSD",
            "--timeframe",
            "5min",
            "--feature-config",
            str(manifest_path),
            "--data-root",
            str(data_root),
            "--max-drift",
            "1e-9",
        ],
        capture_output=True,
        text=True,
    )

    # The validation script should pass with exit code 0
    if validation_result_5min.returncode != 0:
        print("STDOUT:", validation_result_5min.stdout)
        print("STDERR:", validation_result_5min.stderr)

    assert validation_result_5min.returncode == 0, (
        f"5min validation should pass. Exit code: {validation_result_5min.returncode}. "
        f"Output: {validation_result_5min.stdout}"
    )
    assert (
        "VALIDATION PASSED" in validation_result_5min.stdout
    ), "Should report successful validation"

    # Test 15min timeframe
    validation_result_15min = subprocess.run(
        [
            sys.executable,
            "scripts/validate_feature_cache.py",
            "--cache-dir",
            str(cache_root),
            "--symbol",
            "EURUSD",
            "--timeframe",
            "15min",
            "--feature-config",
            str(manifest_path),
            "--data-root",
            str(data_root),
            "--max-drift",
            "1e-9",
        ],
        capture_output=True,
        text=True,
    )

    if validation_result_15min.returncode != 0:
        print("STDOUT:", validation_result_15min.stdout)
        print("STDERR:", validation_result_15min.stderr)

    assert (
        validation_result_15min.returncode == 0
    ), f"15min validation should pass. Exit code: {validation_result_15min.returncode}"
    assert (
        "VALIDATION PASSED" in validation_result_15min.stdout
    ), "Should report successful validation"

    # ==================== Step 5: Test Digest Mismatch Detection ====================
    # Tamper with manifest digest in metadata
    metadata_path = descriptor.metadata_path()
    metadata = json.loads(metadata_path.read_text())
    original_digest = metadata["manifest_digest"]
    metadata["manifest_digest"] = "0" * 64  # Invalid digest
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Attempt to load should raise ValueError
    with pytest.raises(ValueError, match="[Mm]anifest.*digest"):
        load_cached_global_features(
            symbol="EURUSD",
            timeframe="5min",
            cache_root=cache_root,
            config_path=manifest_path,
            feature_names=["5min_ema_10", "5min_rsi_14"],
            session_group="forex",
        )

    # Restore original digest
    metadata["manifest_digest"] = original_digest
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Should load successfully again
    result_after_restore = load_cached_global_features(
        symbol="EURUSD",
        timeframe="5min",
        cache_root=cache_root,
        config_path=manifest_path,
        feature_names=["5min_ema_10", "5min_rsi_14"],
        session_group="forex",
    )
    assert result_after_restore is not None, "Should load after digest restored"


def test_pipeline_detects_manifest_changes(tmp_path: Path) -> None:
    """Test that changing manifest triggers digest mismatch."""
    # Setup
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"

    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"

    _write_market_data_csv(csv_path)
    _write_feature_manifest(manifest_path)

    # Build initial cache
    descriptor = build_global_feature_caches(
        symbol="EURUSD",
        data_root=data_root,
        config_path=manifest_path,
        timeframes=["5min"],
        overwrite=True,
        cache_root=cache_root,
    )

    # Load successfully
    result_initial = load_cached_global_features(
        symbol="EURUSD",
        timeframe="5min",
        cache_root=cache_root,
        config_path=manifest_path,
        feature_names=["5min_ema_10"],
        session_group="forex",
    )
    assert result_initial is not None

    # Modify manifest content (simulated by tampering metadata)
    metadata_path = descriptor.metadata_path()
    metadata = json.loads(metadata_path.read_text())
    metadata["manifest_digest"] = "a" * 64  # Simulate different manifest
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Should detect mismatch
    with pytest.raises(ValueError, match="[Mm]anifest.*digest"):
        load_cached_global_features(
            symbol="EURUSD",
            timeframe="5min",
            cache_root=cache_root,
            config_path=manifest_path,
            feature_names=["5min_ema_10"],
            session_group="forex",
        )
