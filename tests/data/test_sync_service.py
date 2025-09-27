# Validates: [DH-F.1]
from __future__ import annotations

from datetime import date
from pathlib import Path

from trading_platform.data.sync_service import (
    download_and_save_data,
    get_last_sync_date,
)


def test_get_last_sync_date_from_filenames():
    """Test that get_last_sync_date correctly extracts latest date."""
    # Create a list of dummy filenames
    dummy_files = [
        Path("eurusd_interval_min_1_20240101_20240531.csv"),
        Path("eurusd_interval_min_1_20240601_20240823.csv"),
    ]

    # Call get_last_sync_date with this list
    result = get_last_sync_date(dummy_files)

    # Assert that it returns a datetime.date object for 2024-08-23
    assert result is not None
    assert isinstance(result, date)
    assert result == date(2024, 8, 23)


def test_get_last_sync_date_with_no_files() -> None:
    assert get_last_sync_date([]) is None


def test_get_last_sync_date_ignores_unmatched_files() -> None:
    dummy_files = [Path("eurusd_bad_filename.csv")]
    assert get_last_sync_date(dummy_files) is None


def test_get_last_sync_date_skips_invalid_dates() -> None:
    files = [Path("eurusd_interval_min_1_20240101_20240230.csv")]
    assert get_last_sync_date(files) is None


def test_get_last_sync_date_with_older_file_after_newer() -> None:
    """Test that older files don't replace newer latest dates."""
    # Create files where the second one is older than the first
    dummy_files = [
        Path("eurusd_interval_min_1_20240601_20240823.csv"),  # Newer date (Aug 23)
        Path("eurusd_interval_min_1_20240101_20240531.csv"),  # Older date (May 31)
    ]

    result = get_last_sync_date(dummy_files)

    # Should still return the newer date (Aug 23), not the older one
    assert result == date(2024, 8, 23)


def test_download_and_save_data_placeholder() -> None:
    # Placeholder must be callable without side effects
    # Should not raise any exceptions
    download_and_save_data("EUR/USD", date.today(), date.today(), Path("."))
