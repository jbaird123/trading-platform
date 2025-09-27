"""Updated tests for trading_platform.data.loader using convention-based data loading.

These tests have been updated to use the new load_instrument_data function
instead of the removed load_from_catalog function.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from trading_platform.data.loader import load_instrument_data


def _write_sample_csv(path: Path) -> None:
    """Write sample CSV data for testing."""
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2023-01-01 00:00:00+00:00,1,2,0.5,1.5,10",
                "2023-01-01 01:00:00+00:00,1,2,0.5,1.6,10",
                "2023-01-01 02:00:00+00:00,1,2,0.5,1.7,10",
            ]
        )
    )


def _setup_data_directory(base_path: Path) -> None:
    """Set up full data directory structure for testing."""
    # Create directories
    full_dir = base_path / "full" / "eurusd"
    inc_dir = base_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)
    
    # Create base file
    base_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    _write_sample_csv(base_file)
    
    return full_dir, inc_dir


# --- Happy-path loader behaviour -------------------------------------------------


def test_load_instrument_data_basic_loading(tmp_path: Path) -> None:
    """Test that load_instrument_data loads data correctly."""
    _setup_data_directory(tmp_path)

    # The new function signature is: load_instrument_data(symbol, data_root)
    df, flags = load_instrument_data("EUR/USD", tmp_path)

    assert flags == []
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert len(df) == 3  # original data without resampling


# --- Validation error coverage ---------------------------------------------------


def test_loader_symbol_not_found(tmp_path: Path) -> None:
    """Test loader handles symbol not found in data directory."""
    # Create directory but no data for FAKE symbol
    tmp_path.mkdir(exist_ok=True)
    
    with pytest.raises(FileNotFoundError, match="No data files found for symbol"):
        load_instrument_data("FAKE", tmp_path)


def test_loader_empty_data_from_csv(tmp_path: Path) -> None:
    """Test loader handles empty CSV files."""
    full_dir, _ = _setup_data_directory(tmp_path)
    
    # Overwrite with empty file
    csv_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    csv_file.write_text("timestamp,open,high,low,close,volume\n")

    with pytest.raises(ValueError, match="Base data file is empty"):
        load_instrument_data("EUR/USD", tmp_path)


# --- Additional behavioural branches --------------------------------------------


def test_loader_with_minute_data(tmp_path: Path) -> None:
    """Test loader handles minute-level data correctly."""
    full_dir, _ = _setup_data_directory(tmp_path)
    
    # Overwrite with minute-level data
    csv_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    csv_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-01 00:00:00+00:00,1.0,1.1,0.9,1.05,1000\n"
        "2023-01-01 00:01:00+00:00,1.05,1.15,0.95,1.10,1100\n"
    )

    df, flags = load_instrument_data("EUR/USD", tmp_path)

    assert not flags
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_loader_returns_original_rows(tmp_path: Path) -> None:
    """Test loader returns original rows intact."""
    _setup_data_directory(tmp_path)

    df, flags = load_instrument_data("EUR/USD", tmp_path)

    assert not flags
    assert len(df) == 3  # no resampling, original rows retained
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_load_instrument_data_with_symbol_normalization(tmp_path: Path) -> None:
    """Test that load_instrument_data works with symbol normalization."""
    _setup_data_directory(tmp_path)

    # Test that EUR_USD finds eurusd directory
    df, flags = load_instrument_data("EUR_USD", tmp_path)

    assert not flags
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    # Test that EUR/USD (another format) also works
    df2, flags2 = load_instrument_data("EUR/USD", tmp_path)

    assert not flags2
    assert not df2.empty

    # Verify both return the same data
    pd.testing.assert_frame_equal(df, df2)


def test_load_instrument_data_loads_incremental_data(tmp_path: Path) -> None:
    """Test that load_instrument_data can load and combine incremental data files."""
    full_dir, inc_dir = _setup_data_directory(tmp_path)

    # Create incremental files
    inc_file1 = inc_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    inc_file1.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-02 00:00:00+00:00,1.10,1.20,1.00,1.15,1200\n"
    )

    inc_file2 = inc_dir / "eurusd_interval_minute_1_20230103_20230103.csv"
    inc_file2.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-03 00:00:00+00:00,1.15,1.25,1.05,1.20,1300\n"
    )

    # Test loading - should combine all files
    df, flags = load_instrument_data("EURUSD", tmp_path)

    # Assert that the returned DataFrame contains data from all files
    assert not flags
    assert len(df) == 5  # 3 base + 1 + 1 incremental

    # Assert that the index is sorted and unique
    assert df.index.is_monotonic_increasing
    assert df.index.is_unique

    # Verify data spans from base file to incremental files
    assert df.index[0].strftime("%Y-%m-%d") == "2023-01-01"
    assert df.index[-1].strftime("%Y-%m-%d") == "2023-01-03"


def test_loader_skips_empty_incremental_files(tmp_path: Path) -> None:
    """Empty incremental CSV files must not be appended to the dataset."""
    full_dir, inc_dir = _setup_data_directory(tmp_path)

    # Create empty incremental file
    empty_file = inc_dir / "eurusd_interval_minute_1_20240101_20240101.csv"
    empty_file.write_text("timestamp,open,high,low,close,volume\n")

    df, flags = load_instrument_data("EURUSD", tmp_path)

    assert len(df) == 3  # Only base data, empty incremental ignored
    assert flags == []


def test_loader_ignores_failed_incremental_files(tmp_path: Path) -> None:
    """Incremental loader failures are ignored while base data is returned."""
    full_dir, inc_dir = _setup_data_directory(tmp_path)

    # Create bad incremental file
    bad_file = inc_dir / "eurusd_interval_minute_1_bad_bad.csv"
    bad_file.write_text("garbage\n")

    from unittest.mock import patch

    from trading_platform.data import loader as loader_module

    real_load = loader_module.load_and_normalize_data

    def side_effect(path: Path):
        if "bad_bad" in str(path):
            raise RuntimeError("failed incremental load")
        return real_load(path)

    with patch(
        "trading_platform.data.loader.load_and_normalize_data",
        side_effect=side_effect,
    ):
        df, flags = load_instrument_data("EURUSD", tmp_path)

    assert len(df) == 3  # Only base data, failed incremental ignored
    assert flags == []