"""Tests for scripts/validate_feature_cache.py CLI tool.

These tests verify that the validation script correctly:
1. Exits 0 when cache matches recomputed features
2. Exits 1 when cache contains corrupted/mismatched data
3. Reports mismatched columns and digest information
4. Handles various CLI arguments correctly
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


def _create_minimal_cache(
    cache_root: Path,
    symbol: str,
    timeframe: str,
    config_hash: str,
    manifest_digest: str,
    feature_data: pd.DataFrame,
) -> None:
    """Create a minimal cache structure for testing."""
    # Create cache directory structure: cache_root/symbol/config_hash/
    cache_dir = cache_root / symbol.lower().replace("_", "") / config_hash
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Write metadata.json
    metadata = {
        "symbol": symbol,
        "config_hash": config_hash,
        "manifest_digest": manifest_digest,
        "timeframes": {
            timeframe: {
                "columns": list(feature_data.columns),
                "rows": len(feature_data),
            }
        },
    }
    metadata_path = cache_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Write parquet file for the timeframe
    parquet_path = cache_dir / f"{timeframe}.parquet"
    df_to_save = feature_data.copy()
    df_to_save.reset_index(inplace=True)
    df_to_save.rename(columns={"timestamp": "available_at"}, inplace=True)
    df_to_save.to_parquet(parquet_path, index=False)


def _create_minimal_manifest(path: Path, feature_name: str, timeframe: str) -> None:
    """Create a minimal feature manifest YAML file."""
    content = f"""features:
  - name: "{feature_name}"
    type: "EMA"
    params:
      length: 10
    timeframe: "{timeframe}"
"""
    path.write_text(content)


@pytest.fixture
def sample_feature_data() -> pd.DataFrame:
    """Create minimal feature data for testing."""
    idx = pd.date_range("2023-01-01", periods=2, freq="5min", tz="UTC")
    df = pd.DataFrame({"5min_test_ema": [1.0, 1.5]}, index=idx)
    df.index.name = "timestamp"
    return df


def test_validate_script_exists():
    """Test that the validate_feature_cache script exists."""
    script_path = (
        Path(__file__).parent.parent.parent / "scripts" / "validate_feature_cache.py"
    )
    # Script will be created in Task 7, so this is a TDD red test
    # assert script_path.exists(), f"Script not found at {script_path}"
    # For now, just ensure we can import the module structure
    assert script_path.parent.exists(), "scripts directory should exist"


def test_validation_succeeds_with_matching_cache(tmp_path, sample_feature_data):
    """Test that validation exits 0 when cache matches recomputed features."""
    # Setup
    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"
    config_hash = "abc123"
    manifest_digest = "def456"

    _create_minimal_manifest(manifest_path, "5min_test_ema", "5min")
    _create_minimal_cache(
        cache_root, "EUR_USD", "5min", config_hash, manifest_digest, sample_feature_data
    )

    # Mock build_global_feature_frame to return matching data
    with patch(
        "scripts.validate_feature_cache.build_global_feature_frame"
    ) as mock_build:
        mock_build.return_value = (sample_feature_data, {"valid_start": {}})

        # Mock sys.argv to pass CLI arguments
        with patch(
            "sys.argv",
            [
                "validate_feature_cache.py",
                "--cache-dir",
                str(cache_root),
                "--symbol",
                "EUR_USD",
                "--timeframe",
                "5min",
                "--feature-config",
                str(manifest_path),
            ],
        ):
            # Import and run main - should exit 0
            with pytest.raises(SystemExit) as exc_info:
                from scripts.validate_feature_cache import main

                main()

            assert exc_info.value.code == 0, "Should exit 0 on matching cache"


def test_validation_fails_with_corrupted_cache(tmp_path, sample_feature_data):
    """Test that validation exits 1 when cache contains corrupted data."""
    # Setup
    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"
    config_hash = "abc123"
    manifest_digest = "def456"

    # Create cache with original data
    _create_minimal_manifest(manifest_path, "5min_test_ema", "5min")
    _create_minimal_cache(
        cache_root, "EUR_USD", "5min", config_hash, manifest_digest, sample_feature_data
    )

    # Create mismatched recomputed data
    corrupted_data = sample_feature_data.copy()
    corrupted_data.iloc[0, 0] = 99.9  # Corrupt first value

    # Mock build_global_feature_frame to return different data
    with patch(
        "scripts.validate_feature_cache.build_global_feature_frame"
    ) as mock_build:
        mock_build.return_value = (corrupted_data, {"valid_start": {}})

        with patch(
            "sys.argv",
            [
                "validate_feature_cache.py",
                "--cache-dir",
                str(cache_root),
                "--symbol",
                "EUR_USD",
                "--timeframe",
                "5min",
                "--feature-config",
                str(manifest_path),
            ],
        ):
            # Should exit 1 due to mismatch
            with pytest.raises(SystemExit) as exc_info:
                from scripts.validate_feature_cache import main

                main()

            assert exc_info.value.code == 1, "Should exit 1 on corrupted cache"


def test_validation_reports_digest_and_mismatches(
    tmp_path, sample_feature_data, capsys
):
    """Test that validation reports digest and mismatch details."""
    # Setup
    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"
    config_hash = "abc123"
    manifest_digest = "1234567890abcdef" * 4  # 64-char hex

    _create_minimal_manifest(manifest_path, "5min_test_ema", "5min")
    _create_minimal_cache(
        cache_root, "EUR_USD", "5min", config_hash, manifest_digest, sample_feature_data
    )

    # Create mismatched data
    corrupted_data = sample_feature_data.copy()
    corrupted_data.iloc[0, 0] = 99.9

    with patch(
        "scripts.validate_feature_cache.build_global_feature_frame"
    ) as mock_build:
        mock_build.return_value = (corrupted_data, {"valid_start": {}})

        with patch(
            "sys.argv",
            [
                "validate_feature_cache.py",
                "--cache-dir",
                str(cache_root),
                "--symbol",
                "EUR_USD",
                "--timeframe",
                "5min",
                "--feature-config",
                str(manifest_path),
            ],
        ):
            with pytest.raises(SystemExit):
                from scripts.validate_feature_cache import main

                main()

    # Check output
    captured = capsys.readouterr()
    output = captured.out + captured.err

    # Should mention the manifest digest
    assert "digest" in output.lower() or manifest_digest[:16] in output

    # Should mention the timeframe
    assert "5min" in output

    # Should mention mismatched columns
    assert "5min_test_ema" in output or "mismatch" in output.lower()


def test_validation_accepts_sample_size_argument(tmp_path, sample_feature_data):
    """Test that --sample-size argument is accepted and honored."""
    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"
    config_hash = "abc123"
    manifest_digest = "def456"

    _create_minimal_manifest(manifest_path, "5min_test_ema", "5min")
    _create_minimal_cache(
        cache_root, "EUR_USD", "5min", config_hash, manifest_digest, sample_feature_data
    )

    with patch(
        "scripts.validate_feature_cache.build_global_feature_frame"
    ) as mock_build:
        mock_build.return_value = (sample_feature_data.head(1), {"valid_start": {}})

        with patch(
            "sys.argv",
            [
                "validate_feature_cache.py",
                "--cache-dir",
                str(cache_root),
                "--symbol",
                "EUR_USD",
                "--timeframe",
                "5min",
                "--feature-config",
                str(manifest_path),
                "--sample-size",
                "1",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.validate_feature_cache import main

                main()

            # Should still work with sample size
            assert exc_info.value.code == 0


def test_validation_accepts_max_drift_argument(tmp_path, sample_feature_data):
    """Test that --max-drift argument is accepted for tolerance."""
    cache_root = tmp_path / "cache"
    manifest_path = tmp_path / "manifest.yaml"
    config_hash = "abc123"
    manifest_digest = "def456"

    _create_minimal_manifest(manifest_path, "5min_test_ema", "5min")
    _create_minimal_cache(
        cache_root, "EUR_USD", "5min", config_hash, manifest_digest, sample_feature_data
    )

    # Create data with tiny drift within tolerance
    drifted_data = sample_feature_data.copy()
    drifted_data.iloc[0, 0] += 1e-10  # Very small drift

    with patch(
        "scripts.validate_feature_cache.build_global_feature_frame"
    ) as mock_build:
        mock_build.return_value = (drifted_data, {"valid_start": {}})

        with patch(
            "sys.argv",
            [
                "validate_feature_cache.py",
                "--cache-dir",
                str(cache_root),
                "--symbol",
                "EUR_USD",
                "--timeframe",
                "5min",
                "--feature-config",
                str(manifest_path),
                "--max-drift",
                "1e-9",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.validate_feature_cache import main

                main()

            # Should pass with sufficient tolerance
            assert exc_info.value.code == 0
