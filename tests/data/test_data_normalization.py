from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from trading_platform.data.schema import load_and_normalize_data
from trading_platform.reporting.brief import compute_data_quality


# Add test for data quality score (Task 2.5–2.8)
def test_compute_data_quality_score():
    # Create DataFrame with NaNs and duplicate index
    idx = pd.to_datetime(
        [
            "2023-01-01",
            "2023-01-02",
            "2023-01-03",
            "2023-01-04",
            "2023-01-05",
            "2023-01-03",
        ]
    )  # Add duplicate
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5, 6],
            "high": [2, 3, 4, 5, 6, 7],
            "low": [0, 1, 2, 3, 4, np.nan],
            "close": [1, 2, 3, 4, 5, 6],
            "volume": [100, 200, 300, 400, 500, 600],
        },
        index=idx,
    )
    # 1 NaN, 1 duplicate
    result = compute_data_quality(df)
    # Expected score: start at 1.0, -0.5 for NaN, -0.001 for duplicate
    expected_score = 1.0 - 0.5 - min(0.5, 1 / 1000.0)
    expected_score = max(0.0, expected_score)
    assert "quality_score" in result
    assert abs(result["quality_score"] - expected_score) < 1e-6


@pytest.fixture
def ohlcv_columns():
    """Provides the standard OHLCV column names."""
    return ["open", "high", "low", "close", "volume"]


def test_load_and_normalize_data_handles_naive_timestamps(
    tmp_path: Path, ohlcv_columns: list[str]
):
    """Ensures naive timestamps are correctly localized to UTC."""
    csv_content = "timestamp,open,high,low,close,volume\n"
    csv_content += "2023-01-01 10:00:00,1,2,0,1,100\n"
    csv_file = tmp_path / "naive_data.csv"
    csv_file.write_text(csv_content)

    df, flags = load_and_normalize_data(csv_file)

    assert not df.empty
    assert flags == []
    idx = pd.DatetimeIndex(df.index)
    assert idx.tz is not None
    assert str(idx.tz) == "UTC"
    # Check if the time is correctly interpreted as 10:00 UTC
    assert df.index[0] == pd.Timestamp("2023-01-01 10:00:00", tz="UTC")


def test_load_and_normalize_data_converts_other_timezones_to_utc(
    tmp_path: Path, ohlcv_columns: list[str]
):
    """Ensures timestamps with other timezones are converted to UTC."""
    csv_content = "timestamp,open,high,low,close,volume\n"
    # EST is UTC-5
    csv_content += "2023-01-01 10:00:00-05:00,1,2,0,1,100\n"
    csv_file = tmp_path / "aware_data.csv"
    csv_file.write_text(csv_content)

    df, flags = load_and_normalize_data(csv_file)

    assert not df.empty
    assert flags == []
    idx2 = pd.DatetimeIndex(df.index)
    assert idx2.tz is not None
    assert str(idx2.tz) == "UTC"
    # 10:00 EST should be 15:00 UTC
    assert df.index[0] == pd.Timestamp("2023-01-01 15:00:00", tz="UTC")


@pytest.mark.parametrize(
    "header, row_data, expected_flag_content",
    [
        (
            "timestamp,open,high,low",  # Missing close, volume
            "1,2,3,4",
            "missing=['close', 'volume']",
        ),
        (
            "timestamp,open,high,low,close,volume,extra_col",  # Unknown column
            "1,2,3,4,5,6,7",
            "unknown=['extra_col']",
        ),
        (
            "open,high,low,close,volume",  # Missing timestamp
            "1,2,3,4,5",
            "missing_timestamp",
        ),
    ],
)
def test_load_and_normalize_data_generates_quality_flags(
    tmp_path: Path, header: str, row_data: str, expected_flag_content: str
):
    """
    Validates that load_and_normalize_data returns appropriate quality flags
    for malformed CSV files, covering requirement [DH-2.7].
    """
    csv_content = f"{header}\n{row_data}"
    csv_file = tmp_path / "malformed_data.csv"
    csv_file.write_text(csv_content)

    df, flags = load_and_normalize_data(csv_file)

    assert df.empty
    assert len(flags) > 0
    # Check that the expected error signature is in one of the flags
    assert any(expected_flag_content in flag for flag in flags)
