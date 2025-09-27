from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import sys

import pandas as pd
import pytest

from trading_platform.data import sync_service as ss


def test_get_last_sync_date_empty() -> None:
    assert ss.get_last_sync_date([]) is None


def test_get_last_sync_date_parses_latest(tmp_path: Path) -> None:
    files = [
        Path("eurusd_interval_min_1_20230101_20230131.csv"),
        Path("eurusd_interval_min_1_20230201_20230228.csv"),
    ]

    result = ss.get_last_sync_date(files)
    assert result == date(2023, 2, 28)


def test_is_expected_weekend_gap_true() -> None:
    # Friday 21:00 UTC to Sunday 21:30 UTC (~48.5 hours)
    last_ts = pd.Timestamp("2023-01-06T21:00:00+00:00")
    first_ts = pd.Timestamp("2023-01-08T21:30:00+00:00")

    assert ss._is_expected_weekend_gap(last_ts, first_ts)


def test_is_expected_weekend_gap_false() -> None:
    # Simple 10 hour gap not a weekend
    last_ts = pd.Timestamp("2023-01-03T10:00:00+00:00")
    first_ts = pd.Timestamp("2023-01-03T20:00:00+00:00")

    assert not ss._is_expected_weekend_gap(last_ts, first_ts)


def test_is_during_market_hours_and_cross_weekend() -> None:
    # Cross-weekend should return False
    last_ts = pd.Timestamp("2023-01-06T21:00:00+00:00")
    first_ts = pd.Timestamp("2023-01-08T21:30:00+00:00")

    assert not ss._is_during_market_hours(last_ts, first_ts)


def test_verify_data_continuity_no_previous(tmp_path: Path, capsys) -> None:
    # No full or incremental dirs created
    new_file = tmp_path / "incremental" / "eurusd" / "x.csv"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("timestamp,open,high,low,close,volume\n")

    ss.verify_data_continuity("EUR/USD", tmp_path, new_file)
    captured = capsys.readouterr()
    assert "No previous files found" in captured.out


def test_verify_data_continuity_new_file_empty(tmp_path: Path, capsys) -> None:
    # Create a previous file with data
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)
    prev = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    prev.write_text(
        "timestamp,open,high,low,close,volume\n2023-01-01 00:00:00+00:00,1,2,0.5,1.5,10\n"
    )

    # New file is empty
    new_file = tmp_path / "incremental" / "eurusd" / "new.csv"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("timestamp,open,high,low,close,volume\n")

    ss.verify_data_continuity("EUR/USD", tmp_path, new_file)
    captured = capsys.readouterr()
    assert "New file is empty" in captured.out


def test_verify_data_continuity_unexpected_gap_raises(tmp_path: Path) -> None:
    # Previous file with a timestamp
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)
    prev = full_dir / "eurusd_interval_minute_1_20230103_20230103.csv"
    prev.write_text(
        "timestamp,open,high,low,close,volume\n2023-01-03 10:00:00+00:00,1,2,0.5,1.5,10\n"
    )

    # New file with a 10-minute gap in trading hours
    new_file = tmp_path / "incremental" / "eurusd" / "new.csv"
    new_file.parent.mkdir(parents=True)
    new_file.write_text(
        "timestamp,open,high,low,close,volume\n2023-01-03 10:10:00+00:00,1,2,0.5,1.5,10\n"
    )

    with pytest.raises(RuntimeError, match="Unexpected data gap detected"):
        ss.verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_download_and_save_data_success(monkeypatch, tmp_path: Path) -> None:
    # Create fake dukascopy_python module
    class FakeDuka:
        INTERVAL_MIN_1 = 1
        OFFER_SIDE_BID = 1

        @staticmethod
        def fetch(instrument, interval, offer_side, start, end):
            # Return a small DataFrame with datetime index
            idx = pd.date_range(start="2023-01-01", periods=2, freq="min", tz="UTC")
            df = pd.DataFrame({"open": [1.0, 1.1]}, index=idx)
            return df

    monkeypatch.setitem(sys.modules, "dukascopy_python", FakeDuka)

    # Patch verify_data_continuity to avoid raising in this unit test
    monkeypatch.setattr(ss, "verify_data_continuity", lambda *a, **k: None)

    # Run downloader with a valid date range
    start = date(2023, 1, 1)
    end = date(2023, 1, 2)

    ss.download_and_save_data("EUR/USD", start, end, tmp_path)

    # Verify an incremental file was created
    inc_dir = tmp_path / "incremental" / "eurusd"
    files = list(inc_dir.glob("*.csv"))
    assert files, "No file was written by download_and_save_data"
# Validates: [DH-F.1]

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
    
    # Set up directory structure with new convention
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)
    
    # Create existing file ending on Friday
    existing_data = pd.DataFrame({
        'timestamp': ['2025-08-22 20:59:00+00:00'],
        'open': [1.1720], 'high': [1.1721], 'low': [1.1720], 
        'close': [1.1721], 'volume': [100]
    })
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250822_20250822.csv"
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
    
    # Set up directory structure with new convention
    full_symbol_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)
    
    # Create existing file ending on Wednesday morning
    existing_data = pd.DataFrame({
        'timestamp': ['2025-08-20 10:00:00+00:00'],
        'open': [1.1720], 'high': [1.1721], 'low': [1.1720],
        'close': [1.1721], 'volume': [100]
    })
    existing_file = full_symbol_dir / "eurusd_interval_minute_1_20250820_20250820.csv"
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
