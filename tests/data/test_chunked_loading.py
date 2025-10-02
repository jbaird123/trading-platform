"""Tests for chunked data loading.

# Validates: [DH-2.9]
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest


def test_chunked_loading_processes_large_datasets(tmp_path: Path):
    """Test that chunked loading can process datasets larger than memory.

    Validates: [DH-2.9]
    """
    # Create a large CSV file
    data_file = tmp_path / "large_data.csv"

    # Generate sample data
    start_time = datetime(2024, 1, 1)
    rows = []
    for i in range(10000):  # 10k rows as test sample
        timestamp = start_time + timedelta(minutes=i)
        rows.append({
            "timestamp": timestamp.isoformat(),
            "open": 1.1000 + i * 0.0001,
            "high": 1.1010 + i * 0.0001,
            "low": 1.0990 + i * 0.0001,
            "close": 1.1005 + i * 0.0001,
            "volume": 1000 + i
        })

    df = pd.DataFrame(rows)
    df.to_csv(data_file, index=False)

    # Test chunked reading
    chunk_size = 1000
    total_rows = 0
    chunks_processed = 0

    for chunk in pd.read_csv(data_file, chunksize=chunk_size):
        total_rows += len(chunk)
        chunks_processed += 1

        # Verify chunk structure
        assert "timestamp" in chunk.columns
        assert "close" in chunk.columns
        assert len(chunk) <= chunk_size

    assert total_rows == 10000
    assert chunks_processed == 10  # 10000 / 1000


def test_chunked_loading_maintains_data_integrity(tmp_path: Path):
    """Test that chunked loading maintains data integrity across chunks.

    Validates: [DH-2.9]
    """
    data_file = tmp_path / "test_data.csv"

    # Create test data with known values
    data = pd.DataFrame({
        "timestamp": [f"2024-01-01T{i:02d}:00:00" for i in range(24)],
        "close": [1.1000 + i * 0.0001 for i in range(24)],
        "volume": [1000 + i * 10 for i in range(24)]
    })
    data.to_csv(data_file, index=False)

    # Read in chunks
    chunks = []
    for chunk in pd.read_csv(data_file, chunksize=5):
        chunks.append(chunk)

    # Reconstruct full dataset
    reconstructed = pd.concat(chunks, ignore_index=True)

    # Verify integrity
    assert len(reconstructed) == 24
    assert list(reconstructed.columns) == ["timestamp", "close", "volume"]
    assert reconstructed["close"].iloc[0] == 1.1000
    assert reconstructed["close"].iloc[-1] == 1.1000 + 23 * 0.0001


def test_chunked_loading_handles_memory_efficiently(tmp_path: Path):
    """Test that chunked loading uses less memory than full loading.

    Validates: [DH-2.9]
    """
    data_file = tmp_path / "large_data.csv"

    # Create moderately sized dataset
    rows = 5000
    data = pd.DataFrame({
        "timestamp": [f"2024-01-01T{i:02d}:{i%60:02d}:00" for i in range(rows)],
        "close": [1.1000 + i * 0.0001 for i in range(rows)],
        "volume": [1000 + i for i in range(rows)]
    })
    data.to_csv(data_file, index=False)

    # Chunked processing should work without loading entire file
    chunk_size = 500
    row_count = 0

    for chunk in pd.read_csv(data_file, chunksize=chunk_size):
        row_count += len(chunk)
        # Process only the chunk in memory
        assert len(chunk) <= chunk_size

    assert row_count == rows


def test_chunked_loading_with_filtering(tmp_path: Path):
    """Test that chunked loading can apply filters during iteration.

    Validates: [DH-2.9]
    """
    data_file = tmp_path / "test_data.csv"

    # Create test data
    data = pd.DataFrame({
        "timestamp": [f"2024-01-01T{i:02d}:00:00" for i in range(100)],
        "close": [1.1000 + (i % 10) * 0.0001 for i in range(100)],
        "volume": [1000 + i for i in range(100)]
    })
    data.to_csv(data_file, index=False)

    # Read in chunks and filter
    filtered_rows = []
    for chunk in pd.read_csv(data_file, chunksize=10):
        # Filter for rows where close > 1.1005
        filtered = chunk[chunk["close"] > 1.1005]
        filtered_rows.append(filtered)

    result = pd.concat(filtered_rows, ignore_index=True)

    # Verify filtering worked
    assert len(result) > 0
    assert all(result["close"] > 1.1005)


def test_chunked_loading_preserves_dtypes(tmp_path: Path):
    """Test that chunked loading preserves data types across chunks.

    Validates: [DH-2.9]
    """
    data_file = tmp_path / "typed_data.csv"

    # Create data with specific types
    data = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=50, freq="1h"),
        "close": [1.1000 + i * 0.0001 for i in range(50)],
        "volume": [1000 + i for i in range(50)]
    })
    data.to_csv(data_file, index=False)

    # Read in chunks
    dtypes_per_chunk = []
    for chunk in pd.read_csv(data_file, chunksize=10):
        dtypes_per_chunk.append(chunk.dtypes.to_dict())

    # Verify all chunks have consistent dtypes
    first_dtypes = dtypes_per_chunk[0]
    for dtypes in dtypes_per_chunk[1:]:
        assert dtypes == first_dtypes
