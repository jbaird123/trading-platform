# Validates: [DH-F.1]
from __future__ import annotations

from datetime import date
from pathlib import Path

from trading_platform.data.sync_service import get_last_sync_date


def test_get_last_sync_date_from_filenames():
    """Test that get_last_sync_date correctly extracts latest date."""
    # Create a list of dummy filenames
    dummy_files = [
        Path('eurusd_interval_min_1_20240101_20240531.csv'),
        Path('eurusd_interval_min_1_20240601_20240823.csv')
    ]

    # Call get_last_sync_date with this list
    result = get_last_sync_date(dummy_files)

    # Assert that it returns a datetime.date object for 2024-08-23
    assert result is not None
    assert isinstance(result, date)
    assert result == date(2024, 8, 23)
