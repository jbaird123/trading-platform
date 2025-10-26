from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from trading_platform.data.integrity_validator import (
    check_time_series_gaps,
    check_timestamp_consistency,
    validate_all_data,
    validate_parquet_file,
)


def test_check_gaps_in_time_series() -> None:
    """Test detection of gaps in time series."""
    # Create sample data with gaps
    dates = pd.date_range("2020-01-01", periods=10, freq="1H")
    # Remove some dates to create gaps
    dates_with_gaps = dates.delete([3, 4, 5])  # 3-hour gap

    df = pd.DataFrame(
        {"timestamp": dates_with_gaps, "value": range(len(dates_with_gaps))}
    )

    gaps = check_time_series_gaps(df, max_gap_minutes=120)

    # Should detect the gap
    assert len(gaps) > 0
    assert gaps[0]["gap_minutes"] >= 180  # 3+ hours


def test_check_timestamp_consistency() -> None:
    """Test detection of timestamp inconsistencies."""
    # Create data with out-of-order timestamps
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2020-01-01 00:00",
                    "2020-01-01 02:00",  # Jump forward
                    "2020-01-01 01:00",  # Jump back (inconsistent!)
                    "2020-01-01 03:00",
                ]
            ),
            "value": [1, 2, 3, 4],
        }
    )

    issues = check_timestamp_consistency(df)

    # Should detect non-monotonic timestamps
    assert len(issues) > 0
    assert any("not monotonically increasing" in issue.lower() for issue in issues)


def test_validate_parquet_file(tmp_path: Path) -> None:
    """Test validation of a parquet file."""
    # Create valid parquet file
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=100, freq="1H"),
            "close": np.random.randn(100) + 100,
        }
    )

    parquet_file = tmp_path / "test_data.parquet"
    df.to_parquet(parquet_file)

    result = validate_parquet_file(parquet_file)

    assert result["file"] == parquet_file
    assert result["status"] == "valid"
    assert isinstance(result["gaps"], list)
    assert isinstance(result["timestamp_issues"], list)


def test_validate_all_instruments(tmp_path: Path) -> None:
    """Test validation across multiple instruments."""
    # Create multiple parquet files
    for instrument in ["EUR_USD", "GBP_USD"]:
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2020-01-01", periods=100, freq="1H"),
                "close": np.random.randn(100) + 100,
            }
        )
        parquet_file = tmp_path / f"{instrument}.parquet"
        df.to_parquet(parquet_file)

    summary = validate_all_data(tmp_path, ["EUR_USD", "GBP_USD"])

    assert "total_files" in summary
    assert summary["total_files"] == 2
    assert "issues" in summary
