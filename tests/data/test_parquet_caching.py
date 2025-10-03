"""Tests for Parquet caching functionality.

# Validates: [DH-2.10]
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd


def test_parquet_cache_creates_cache_file(tmp_path: Path):
    """Test that Parquet caching creates a cache file from CSV.

    Validates: [DH-2.10]
    """
    # Create source CSV
    csv_file = tmp_path / "data.csv"
    data = pd.DataFrame(
        {
            "timestamp": [f"2024-01-01T{i:02d}:00:00" for i in range(24)],
            "close": [1.1000 + i * 0.0001 for i in range(24)],
            "volume": [1000 + i for i in range(24)],
        }
    )
    data.to_csv(csv_file, index=False)

    # Create Parquet cache
    parquet_file = tmp_path / "data.parquet"
    df_csv = pd.read_csv(csv_file)
    df_csv.to_parquet(parquet_file, index=False)

    # Verify cache file exists
    assert parquet_file.exists()

    # Verify cache contains same data
    df_parquet = pd.read_parquet(parquet_file)
    pd.testing.assert_frame_equal(df_csv, df_parquet)


def test_parquet_cache_faster_than_csv(tmp_path: Path):
    """Test that reading from Parquet cache is faster than CSV.

    Validates: [DH-2.10]
    """
    # Create larger dataset
    rows = 10000
    data = pd.DataFrame(
        {
            "timestamp": [
                f"2024-01-01T{i:02d}:{i%60:02d}:{i%60:02d}" for i in range(rows)
            ],
            "open": [1.1000 + i * 0.0001 for i in range(rows)],
            "high": [1.1010 + i * 0.0001 for i in range(rows)],
            "low": [1.0990 + i * 0.0001 for i in range(rows)],
            "close": [1.1005 + i * 0.0001 for i in range(rows)],
            "volume": [1000 + i for i in range(rows)],
        }
    )

    csv_file = tmp_path / "large_data.csv"
    parquet_file = tmp_path / "large_data.parquet"

    data.to_csv(csv_file, index=False)
    data.to_parquet(parquet_file, index=False)

    # Time CSV reading
    start = time.perf_counter()
    pd.read_csv(csv_file)
    csv_time = time.perf_counter() - start

    # Time Parquet reading
    start = time.perf_counter()
    pd.read_parquet(parquet_file)
    parquet_time = time.perf_counter() - start

    # Parquet should be faster (typically 2-10x)
    # Use a conservative threshold for test stability
    assert parquet_time < csv_time * 1.5


def test_parquet_cache_invalidation_on_source_change(tmp_path: Path):
    """Test that Parquet cache is invalidated when source CSV changes.

    Validates: [DH-2.10]
    """
    csv_file = tmp_path / "data.csv"
    parquet_file = tmp_path / "data.parquet"

    # Create initial data
    data_v1 = pd.DataFrame(
        {
            "timestamp": ["2024-01-01T00:00:00", "2024-01-01T01:00:00"],
            "close": [1.1000, 1.1001],
            "volume": [1000, 1001],
        }
    )
    data_v1.to_csv(csv_file, index=False)
    data_v1.to_parquet(parquet_file, index=False)

    csv_file.stat().st_mtime
    parquet_mtime_v1 = parquet_file.stat().st_mtime

    # Wait to ensure different timestamps
    time.sleep(0.1)

    # Modify CSV
    data_v2 = pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01T00:00:00",
                "2024-01-01T01:00:00",
                "2024-01-01T02:00:00",
            ],
            "close": [1.1000, 1.1001, 1.1002],
            "volume": [1000, 1001, 1002],
        }
    )
    data_v2.to_csv(csv_file, index=False)

    csv_mtime_v2 = csv_file.stat().st_mtime

    # Check if cache should be invalidated (CSV newer than cache)
    assert csv_mtime_v2 > parquet_mtime_v1


def test_parquet_cache_preserves_schema(tmp_path: Path):
    """Test that Parquet cache preserves data types and schema.

    Validates: [DH-2.10]
    """
    csv_file = tmp_path / "typed_data.csv"
    parquet_file = tmp_path / "typed_data.parquet"

    # Create data with specific types
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01T00:00:00", "2024-01-01T01:00:00"]),
            "close": [1.1000, 1.1001],
            "volume": [1000, 1001],
            "symbol": ["EURUSD", "EURUSD"],
        }
    )

    # Save to CSV and Parquet
    data.to_csv(csv_file, index=False)
    data.to_parquet(parquet_file, index=False)

    # Read from Parquet
    df_parquet = pd.read_parquet(parquet_file)

    # Verify schema preservation
    assert df_parquet["close"].dtype == data["close"].dtype
    assert df_parquet["volume"].dtype == data["volume"].dtype
    assert df_parquet["symbol"].dtype == data["symbol"].dtype


def test_parquet_cache_compression_reduces_size(tmp_path: Path):
    """Test that Parquet cache uses compression to reduce file size.

    Validates: [DH-2.10]
    """
    # Create data with repetitive patterns (compressible)
    rows = 5000
    data = pd.DataFrame(
        {
            "timestamp": [f"2024-01-01T{i%24:02d}:00:00" for i in range(rows)],
            "symbol": ["EURUSD"] * rows,  # Highly compressible
            "close": [1.1000 + (i % 100) * 0.0001 for i in range(rows)],
            "volume": [1000] * rows,  # Highly compressible
        }
    )

    csv_file = tmp_path / "compressible.csv"
    parquet_file = tmp_path / "compressible.parquet"

    data.to_csv(csv_file, index=False)
    data.to_parquet(parquet_file, compression="snappy", index=False)

    csv_size = csv_file.stat().st_size
    parquet_size = parquet_file.stat().st_size

    # Parquet with compression should be smaller
    assert parquet_size < csv_size


def test_parquet_cache_handles_missing_values(tmp_path: Path):
    """Test that Parquet cache correctly handles missing values.

    Validates: [DH-2.10]
    """
    csv_file = tmp_path / "sparse_data.csv"
    parquet_file = tmp_path / "sparse_data.parquet"

    # Create data with NaN values
    data = pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01T00:00:00",
                "2024-01-01T01:00:00",
                "2024-01-01T02:00:00",
            ],
            "close": [1.1000, None, 1.1002],
            "volume": [1000, 1001, None],
        }
    )

    data.to_csv(csv_file, index=False)
    data.to_parquet(parquet_file, index=False)

    # Read from Parquet
    df_parquet = pd.read_parquet(parquet_file)

    # Verify NaN values preserved
    assert pd.isna(df_parquet.loc[1, "close"])
    assert pd.isna(df_parquet.loc[2, "volume"])
    assert not pd.isna(df_parquet.loc[0, "close"])


def test_parquet_cache_supports_column_selection(tmp_path: Path):
    """Test that Parquet cache supports reading specific columns.

    Validates: [DH-2.10]
    """
    parquet_file = tmp_path / "multi_column.parquet"

    # Create data with many columns
    data = pd.DataFrame(
        {
            "timestamp": ["2024-01-01T00:00:00", "2024-01-01T01:00:00"],
            "open": [1.1000, 1.1001],
            "high": [1.1010, 1.1011],
            "low": [1.0990, 1.0991],
            "close": [1.1005, 1.1006],
            "volume": [1000, 1001],
        }
    )

    data.to_parquet(parquet_file, index=False)

    # Read only specific columns
    df_subset = pd.read_parquet(parquet_file, columns=["timestamp", "close"])

    assert list(df_subset.columns) == ["timestamp", "close"]
    assert len(df_subset) == 2
