from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest


def test_validate_data_requires_data_dir_argument() -> None:
    """Test that validate-data command requires --data-dir argument."""
    result = subprocess.run(
        ["poetry", "run", "tp", "validate-data"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--data-dir" in result.stderr or "required" in result.stderr.lower()


def test_validate_data_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Test that validate-data command prints a summary of results."""
    # Create sample data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create valid parquet file
    valid_file = data_dir / "EUR_USD_1H.parquet"
    df_valid = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=100, freq="h"),
            "open": [1.1] * 100,
            "high": [1.2] * 100,
            "low": [1.0] * 100,
            "close": [1.15] * 100,
            "volume": [1000] * 100,
        }
    )
    df_valid.to_parquet(valid_file)

    # Create file with gaps (24+ hour gap)
    gap_file = data_dir / "GBP_USD_1H.parquet"
    timestamps_with_gap = list(pd.date_range("2020-01-01", periods=50, freq="h"))
    timestamps_with_gap.extend(pd.date_range("2020-01-05", periods=50, freq="h"))
    df_gap = pd.DataFrame(
        {
            "timestamp": timestamps_with_gap,
            "open": [1.3] * 100,
            "high": [1.4] * 100,
            "low": [1.2] * 100,
            "close": [1.35] * 100,
            "volume": [1000] * 100,
        }
    )
    df_gap.to_parquet(gap_file)

    # Run command
    result = subprocess.run(
        ["poetry", "run", "tp", "validate-data", "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
    )

    # Check output contains summary
    output = result.stdout + result.stderr
    assert "Total files checked:" in output or "files" in output.lower()
    assert "issues" in output.lower() or "gaps" in output.lower()


def test_validate_data_returns_nonzero_if_issues_found(tmp_path: Path) -> None:
    """Test that validate-data returns exit code 1 if issues are found."""
    # Create data directory with problematic data
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create file with gaps
    gap_file = data_dir / "EUR_USD_1H.parquet"
    timestamps_with_gap = list(pd.date_range("2020-01-01", periods=50, freq="h"))
    # Add a 3-day gap
    timestamps_with_gap.extend(pd.date_range("2020-01-05", periods=50, freq="h"))
    df_gap = pd.DataFrame(
        {
            "timestamp": timestamps_with_gap,
            "open": [1.1] * 100,
            "high": [1.2] * 100,
            "low": [1.0] * 100,
            "close": [1.15] * 100,
            "volume": [1000] * 100,
        }
    )
    df_gap.to_parquet(gap_file)

    # Run command
    result = subprocess.run(
        ["poetry", "run", "tp", "validate-data", "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
    )

    # Should return non-zero exit code when issues are found
    assert result.returncode == 1
