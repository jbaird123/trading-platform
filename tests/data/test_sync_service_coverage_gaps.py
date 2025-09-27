"""Additional tests to achieve 100% coverage for data/sync_service.py."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from trading_platform.data.sync_service import (
    download_and_save_data,
    verify_data_continuity,
)


def test_verify_data_continuity_no_previous_files(tmp_path):
    """Test verify_data_continuity when no previous files exist."""

    # Set up directory structure
    inc_dir = tmp_path / "incremental" / "eurusd"
    inc_dir.mkdir(parents=True)

    # Create new file
    new_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-24 21:00:00+00:00"],
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    new_file = inc_dir / "eurusd_interval_minute_1_20250824_20250824.csv"
    new_data.to_csv(new_file, index=False)

    # Should not raise an error - just print message about no previous files
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_cannot_read_existing_file(tmp_path):
    """Test verify_data_continuity when existing files cannot be read."""

    # Set up directory structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create corrupted existing file
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    existing_file.write_text("corrupted,data\n")

    # Create new file
    new_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-20 15:00:00+00:00"],
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    new_file = inc_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    new_data.to_csv(new_file, index=False)

    # Should not raise an error - continues despite read error
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_cannot_determine_latest_timestamp(tmp_path):
    """Test when cannot determine latest timestamp from existing files."""

    # Set up directory structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create empty existing file
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    existing_data = pd.DataFrame(
        {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    )
    existing_data.to_csv(existing_file, index=False)

    # Create new file
    new_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-20 15:00:00+00:00"],
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    new_file = inc_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    new_data.to_csv(new_file, index=False)

    # Should not raise error - prints message about no timestamp
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_new_file_empty(tmp_path):
    """Test verify_data_continuity when new file is empty."""

    # Set up directory structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create existing file
    existing_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-20 10:00:00+00:00"],
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    existing_data.to_csv(existing_file, index=False)

    # Create empty new file
    new_data = pd.DataFrame(
        {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    )
    new_file = inc_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    new_data.to_csv(new_file, index=False)

    # Should not raise error - prints message about empty file
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_cannot_read_new_file(tmp_path):
    """Test verify_data_continuity when new file cannot be read."""

    # Set up directory structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create existing file
    existing_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-20 10:00:00+00:00"],
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    existing_data.to_csv(existing_file, index=False)

    # Create corrupted new file
    new_file = inc_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    new_file.write_text("corrupted,data\n")

    # Should not raise error - prints warning about corrupted file
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_gap_during_market_closure(tmp_path):
    """Test verify_data_continuity when gap occurs during market closure."""

    # Set up directory structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create existing file ending on Saturday (market closed)
    existing_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-23 10:00:00+00:00"],  # Saturday
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250823_20250823.csv"
    existing_data.to_csv(existing_file, index=False)

    # Create new file starting on Sunday (market closed)
    new_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-24 15:00:00+00:00"],  # Sunday, but gap > 1 min
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    new_file = inc_dir / "eurusd_interval_minute_1_20250824_20250824.csv"
    new_data.to_csv(new_file, index=False)

    # Should not raise an error - gap during market closure is acceptable
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_small_gap_acceptable(tmp_path):
    """Test verify_data_continuity when gap is <= 1 minute (acceptable)."""

    # Set up directory structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create existing file
    existing_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-20 10:00:00+00:00"],
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    existing_data.to_csv(existing_file, index=False)

    # Create new file with 1-minute gap (acceptable)
    new_data = pd.DataFrame(
        {
            "timestamp": ["2025-08-20 10:01:00+00:00"],  # Only 1 minute gap
            "open": [1.1720],
            "high": [1.1721],
            "low": [1.1720],
            "close": [1.1721],
            "volume": [100],
        }
    )
    new_file = inc_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    new_data.to_csv(new_file, index=False)

    # Should not raise an error - 1-minute gap is acceptable
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_download_and_save_data_start_date_in_future():
    """Test download_and_save_data when start_date is in future."""

    future_date = date.today() + timedelta(days=1)
    today = date.today()

    # Should return early and print message
    download_and_save_data("EUR/USD", future_date, today, Path("/tmp"))


def test_download_and_save_data_end_date_in_future():
    """Test download_and_save_data when end_date is in future."""

    yesterday = date.today() - timedelta(days=1)
    future_date = date.today() + timedelta(days=1)

    with patch("dukascopy_python.fetch") as mock_fetch, patch(
        "trading_platform.data.sync_service.verify_data_continuity"
    ):
        # Create empty DataFrame to simulate no data
        mock_fetch.return_value = pd.DataFrame()

        # Should adjust end_date to today and continue
        download_and_save_data("EUR/USD", yesterday, future_date, Path("/tmp"))

        # Should have been called with adjusted end date
        assert mock_fetch.called


def test_download_and_save_data_no_data_returned(tmp_path):
    """Test download_and_save_data when dukascopy returns no data."""

    yesterday = date.today() - timedelta(days=1)
    today = date.today()

    with patch("dukascopy_python.fetch") as mock_fetch:
        # Return None (no data)
        mock_fetch.return_value = None

        # Should print message and return without error
        download_and_save_data("EUR/USD", yesterday, today, tmp_path)

        assert mock_fetch.called


def test_download_and_save_data_empty_dataframe(tmp_path):
    """Test download_and_save_data when dukascopy returns empty DataFrame."""

    yesterday = date.today() - timedelta(days=1)
    today = date.today()

    with patch("dukascopy_python.fetch") as mock_fetch:
        # Return empty DataFrame
        mock_fetch.return_value = pd.DataFrame()

        # Should print message and return without error
        download_and_save_data("EUR/USD", yesterday, today, tmp_path)

        assert mock_fetch.called


def test_download_and_save_data_fetch_exception(tmp_path):
    """Test download_and_save_data when dukascopy fetch raises exception."""

    yesterday = date.today() - timedelta(days=1)
    today = date.today()

    with patch("dukascopy_python.fetch") as mock_fetch:
        # Raise an exception during fetch
        mock_fetch.side_effect = Exception("Network error")

        # Should catch exception, print error and traceback, but not crash
        download_and_save_data("EUR/USD", yesterday, today, tmp_path)

        assert mock_fetch.called


def test_download_and_save_data_successful_download(tmp_path):
    """Test successful download and save with data."""

    yesterday = date.today() - timedelta(days=1)
    today = date.today()

    # Create sample data
    sample_data = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.1, 1.2],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
            "volume": [100, 110],
        },
        index=pd.date_range("2025-08-20", periods=2, freq="1h"),
    )

    with patch("dukascopy_python.fetch") as mock_fetch, patch(
        "trading_platform.data.sync_service.verify_data_continuity"
    ) as mock_verify:
        # Return sample data
        mock_fetch.return_value = sample_data

        # Should download, save, and verify continuity
        download_and_save_data("EUR/USD", yesterday, today, tmp_path)

        assert mock_fetch.called
        assert mock_verify.called

        # Check that file was created
        expected_file = (
            tmp_path
            / "incremental"
            / "eurusd"
            / f"eurusd_interval_minute_1_{yesterday:%Y%m%d}_{today:%Y%m%d}.csv"
        )
        assert expected_file.exists()
