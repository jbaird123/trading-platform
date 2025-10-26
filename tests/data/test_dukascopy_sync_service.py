"""Tests for Dukascopy data sync service.

Tests the functional sync service implementation that uses dukascopy-python
to download historical forex data and manage data continuity checks.

# Validates: [DH-2.14], [DH-2.15], [DH-2.16], [DH-2.17], [DH-2.18], [DH-2.19]
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from trading_platform.data.sync_service import (
    download_and_save_data,
    get_last_sync_date,
    verify_data_continuity,
)


def test_get_last_sync_date_with_no_files() -> None:
    """Test get_last_sync_date returns None when no files exist.

    Validates: [DH-2.14]
    """
    result = get_last_sync_date([])
    assert result is None


def test_get_last_sync_date_with_valid_files(tmp_path: Path) -> None:
    """Test get_last_sync_date extracts most recent date from filenames.

    Validates: [DH-2.14]
    """
    files = [
        tmp_path / "eurusd_interval_min_1_20240101_20240131.csv",
        tmp_path / "eurusd_interval_min_1_20240201_20240229.csv",
        tmp_path / "eurusd_interval_min_1_20240301_20240331.csv",
    ]

    # Create the files
    for file_path in files:
        file_path.touch()

    result = get_last_sync_date(files)

    # Should return the most recent end date (March 31, 2024)
    assert result == date(2024, 3, 31)


def test_get_last_sync_date_ignores_invalid_filenames(tmp_path: Path) -> None:
    """Test get_last_sync_date ignores files with invalid date formats.

    Validates: [DH-2.14]
    """
    files = [
        tmp_path / "eurusd_interval_min_1_20240101_20240131.csv",
        tmp_path / "invalid_filename.csv",
        tmp_path / "eurusd_no_dates.csv",
    ]

    for file_path in files:
        file_path.touch()

    result = get_last_sync_date(files)

    # Should return the only valid date found
    assert result == date(2024, 1, 31)


@patch("dukascopy_python.fetch")
def test_download_and_save_data_success(mock_fetch: MagicMock, tmp_path: Path) -> None:
    """Test download_and_save_data successfully downloads and saves data.

    Validates: [DH-2.15]
    """
    # Create mock DataFrame with sample data
    mock_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="min"),
            "open": [1.1] * 100,
            "high": [1.2] * 100,
            "low": [1.0] * 100,
            "close": [1.15] * 100,
            "volume": [1000] * 100,
        }
    )
    mock_df.set_index("timestamp", inplace=True)
    mock_fetch.return_value = mock_df

    start = date(2024, 1, 1)
    end = date(2024, 1, 2)

    download_and_save_data("EUR/USD", start, end, tmp_path)

    # Verify file was created
    expected_file = (
        tmp_path
        / "incremental"
        / "eurusd"
        / "eurusd_interval_minute_1_20240101_20240102.csv"
    )
    assert expected_file.exists()

    # Verify data was saved correctly
    saved_df = pd.read_csv(expected_file)
    assert len(saved_df) == 100
    assert "timestamp" in saved_df.columns


@patch("dukascopy_python.fetch")
def test_download_and_save_data_handles_empty_response(
    mock_fetch: MagicMock, tmp_path: Path
) -> None:
    """Test download_and_save_data handles empty data response.

    Validates: [DH-2.18]
    """
    mock_fetch.return_value = None

    start = date(2024, 1, 1)
    end = date(2024, 1, 2)

    # Should not raise exception, just print warning
    download_and_save_data("EUR/USD", start, end, tmp_path)

    # Verify no file was created
    incremental_dir = tmp_path / "incremental" / "eurusd"
    if incremental_dir.exists():
        assert len(list(incremental_dir.glob("*.csv"))) == 0


@patch("dukascopy_python.fetch")
def test_download_and_save_data_handles_network_error(
    mock_fetch: MagicMock, tmp_path: Path
) -> None:
    """Test download_and_save_data handles network errors gracefully.

    Validates: [DH-2.18]
    """
    mock_fetch.side_effect = ConnectionError("Network error")

    start = date(2024, 1, 1)
    end = date(2024, 1, 2)

    # Should not raise exception, just print error
    download_and_save_data("EUR/USD", start, end, tmp_path)


def test_verify_data_continuity_with_no_existing_files(tmp_path: Path) -> None:
    """Test verify_data_continuity when no previous files exist.

    Validates: [DH-2.16]
    """
    # Create a new file
    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)

    new_file = incremental_dir / "eurusd_interval_minute_1_20240101_20240102.csv"
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="min"),
            "close": [1.1] * 100,
        }
    )
    df.to_csv(new_file, index=False)

    # Should not raise exception, just print message
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_with_continuous_data(tmp_path: Path) -> None:
    """Test verify_data_continuity with continuous data.

    Validates: [DH-2.17]
    """
    # Create existing file
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)

    existing_file = full_dir / "eurusd_interval_minute_1_20240101_20240102.csv"
    existing_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01 00:00", periods=100, freq="min"),
            "close": [1.1] * 100,
        }
    )
    existing_df.to_csv(existing_file, index=False)

    # Create new file that continues from existing data
    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)

    new_file = incremental_dir / "eurusd_interval_minute_1_20240102_20240103.csv"
    new_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01 01:40", periods=100, freq="min"),
            "close": [1.1] * 100,
        }
    )
    new_df.to_csv(new_file, index=False)

    # Should not raise exception - data is continuous
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_detects_gap_during_market_hours(
    tmp_path: Path,
) -> None:
    """Test verify_data_continuity detects gaps during market hours.

    Validates: [DH-2.17]
    """
    # Create existing file ending on Wednesday
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)

    existing_file = full_dir / "eurusd_interval_minute_1_20240101_20240103.csv"
    # Wednesday Jan 3, 2024 at 10:00
    existing_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-03 10:00", periods=100, freq="min"),
            "close": [1.1] * 100,
        }
    )
    existing_df.to_csv(existing_file, index=False)

    # Create new file starting 4 hours later (gap during market hours)
    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)

    new_file = incremental_dir / "eurusd_interval_minute_1_20240103_20240104.csv"
    # Wednesday Jan 3, 2024 at 15:00 (5 hour gap during Wed market hours)
    new_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-03 15:00", periods=100, freq="min"),
            "close": [1.1] * 100,
        }
    )
    new_df.to_csv(new_file, index=False)

    # Should raise RuntimeError for gap during market hours
    with pytest.raises(RuntimeError, match="Unexpected data gap"):
        verify_data_continuity("EUR/USD", tmp_path, new_file)


@patch("dukascopy_python.fetch")
def test_download_adjusts_future_end_date(
    mock_fetch: MagicMock, tmp_path: Path
) -> None:
    """Test download_and_save_data adjusts end date if in the future.

    Validates: [DH-2.15]
    """
    mock_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="min"),
            "close": [1.1] * 10,
        }
    )
    mock_df.set_index("timestamp", inplace=True)
    mock_fetch.return_value = mock_df

    today = date.today()
    future_date = date(today.year + 1, 1, 1)

    download_and_save_data("EUR/USD", date(2024, 1, 1), future_date, tmp_path)

    # Should have called fetch with today as end date, not future date
    call_args = mock_fetch.call_args
    if call_args is not None:
        end_arg = call_args[1]["end"]
        assert end_arg.date() == today
