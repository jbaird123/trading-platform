# Validates: [DH-F.1]
from __future__ import annotations

from datetime import date
from pathlib import Path

from trading_platform.data.sync_service import (
    download_and_save_data,
    get_last_sync_date,
    verify_data_continuity,
    _is_expected_weekend_gap,
    _is_during_market_hours,
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


def test_download_and_save_data_with_mock(tmp_path: Path, monkeypatch) -> None:
    """Test download_and_save_data with mocked dukascopy-python."""
    from unittest.mock import patch

    import pandas as pd

    # Mock the dukascopy fetch function to return empty DataFrame
    with patch("dukascopy_python.fetch") as mock_fetch:
        mock_fetch.return_value = pd.DataFrame()

        # Should not raise any exceptions even with no data
        download_and_save_data("EUR/USD", date(2024, 1, 1), date(2024, 1, 1), tmp_path)

        # Verify that fetch was called
        assert mock_fetch.called


def test_is_expected_weekend_gap():
    """Test weekend gap detection logic."""
    import pandas as pd
    
    # Friday evening to Sunday evening (valid weekend gap)
    friday_end = pd.Timestamp('2025-08-22 20:59:00+00:00')
    sunday_start = pd.Timestamp('2025-08-24 21:00:00+00:00')
    assert _is_expected_weekend_gap(friday_end, sunday_start) is True
    
    # Wednesday to Thursday (not a weekend gap)
    wed = pd.Timestamp('2025-08-20 10:00:00+00:00')
    thu = pd.Timestamp('2025-08-21 15:00:00+00:00')
    assert _is_expected_weekend_gap(wed, thu) is False
    
    # Friday to Monday (valid weekend gap)
    friday = pd.Timestamp('2025-08-22 20:30:00+00:00')
    monday = pd.Timestamp('2025-08-25 02:00:00+00:00')
    assert _is_expected_weekend_gap(friday, monday) is True


def test_is_during_market_hours():
    """Test market hours detection logic."""
    import pandas as pd
    
    # Tuesday to Wednesday (during market hours)
    tue = pd.Timestamp('2025-08-19 10:00:00+00:00')
    wed = pd.Timestamp('2025-08-20 15:00:00+00:00')
    assert _is_during_market_hours(tue, wed) is True
    
    # Same day gap (during market hours)
    tue_am = pd.Timestamp('2025-08-19 10:00:00+00:00')
    tue_pm = pd.Timestamp('2025-08-19 15:00:00+00:00')
    assert _is_during_market_hours(tue_am, tue_pm) is True
    
    # Friday to Sunday (weekend, not during market hours)
    friday = pd.Timestamp('2025-08-22 20:59:00+00:00')
    sunday = pd.Timestamp('2025-08-24 21:00:00+00:00')
    assert _is_during_market_hours(friday, sunday) is False


def test_verify_data_continuity_with_weekend_gap(tmp_path: Path):
    """Test that verification accepts valid weekend gaps."""
    import pandas as pd
    
    # Set up directory structure
    full_dir = tmp_path / "full"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)
    
    # Create existing file ending on Friday
    existing_data = pd.DataFrame({
        'timestamp': ['2025-08-22 20:59:00+00:00'],
        'open': [1.1720], 'high': [1.1721], 'low': [1.1720], 
        'close': [1.1721], 'volume': [100]
    })
    existing_file = full_dir / "eurusd_interval_minute_1_20250822_20250822.csv"
    existing_data.to_csv(existing_file, index=False)
    
    # Create new file starting on Sunday
    new_data = pd.DataFrame({
        'timestamp': ['2025-08-24 21:00:00+00:00'],
        'open': [1.1720], 'high': [1.1721], 'low': [1.1720],
        'close': [1.1721], 'volume': [100]
    })
    new_file = inc_dir / "eurusd_interval_minute_1_20250824_20250824.csv"
    new_data.to_csv(new_file, index=False)
    
    # Should not raise an error for weekend gap
    verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_verify_data_continuity_with_market_hours_gap(tmp_path: Path):
    """Test that verification raises error for gaps during market hours."""
    import pandas as pd
    import pytest
    
    # Set up directory structure
    full_dir = tmp_path / "full"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)
    
    # Create existing file ending on Wednesday morning
    existing_data = pd.DataFrame({
        'timestamp': ['2025-08-20 10:00:00+00:00'],
        'open': [1.1720], 'high': [1.1721], 'low': [1.1720],
        'close': [1.1721], 'volume': [100]
    })
    existing_file = full_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    existing_data.to_csv(existing_file, index=False)
    
    # Create new file starting on Wednesday afternoon (gap during market hours)
    new_data = pd.DataFrame({
        'timestamp': ['2025-08-20 15:00:00+00:00'],  # 5 hour gap!
        'open': [1.1720], 'high': [1.1721], 'low': [1.1720],
        'close': [1.1721], 'volume': [100]
    })
    new_file = inc_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
    new_data.to_csv(new_file, index=False)
    
    # Should raise RuntimeError for gap during market hours
    with pytest.raises(RuntimeError, match="Unexpected data gap detected during market hours"):
        verify_data_continuity("EUR/USD", tmp_path, new_file)
