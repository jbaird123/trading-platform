"""Additional tests to achieve 100% branch coverage for DataHandler."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from trading_platform.data.handler import DataHandler, _parse_timeframe_to_minutes


def test_parse_timeframe_minutes_no_match() -> None:
    """Test minute format that doesn't match regex pattern.

    Validates: Branch 49→53 - False branch when MIN/T pattern doesn't match
    """
    # These have 'MIN' or 'T' suffix but invalid format
    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("XMIN")  # No number prefix

    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("T")  # Just 'T' with no number


def test_parse_timeframe_hours_no_match() -> None:
    """Test hour format that doesn't match regex pattern.

    Validates: Branch 55→59 - False branch when H pattern doesn't match
    """
    # Has 'H' suffix but invalid format
    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("XH")  # No number prefix

    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("H")  # Just 'H' with no number


def test_parse_timeframe_weeks_no_match() -> None:
    """Test week format that doesn't match regex pattern.

    Validates: Branch 67→70 - False branch when W pattern doesn't match,
    falls through to ValueError
    """
    # Has 'W' suffix but invalid format
    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("XW")  # No number prefix

    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("W")  # Just 'W' with no number


def test_get_data_cache_hit(tmp_path: Path) -> None:
    """Test get_data when timeframe is already cached.

    Validates: Branch 145→153 - False branch (timeframe in cache),
    skips resampling
    """
    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0, 4.0],
            "high": [1.1, 2.1, 3.1, 4.1],
            "low": [0.9, 1.9, 2.9, 3.9],
            "close": [1.05, 2.05, 3.05, 4.05],
            "volume": [100, 200, 300, 400],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # First request - will resample and cache
        with patch(
            "trading_platform.data.handler.resample_ohlc"
        ) as mock_resample:
            mock_resample.return_value = raw_data.copy()
            result1 = handler.get_data(timeframe="4H")
            assert mock_resample.call_count == 1

        # Second request - should hit cache, no resampling
        with patch(
            "trading_platform.data.handler.resample_ohlc"
        ) as mock_resample:
            result2 = handler.get_data(timeframe="4H")
            # Branch 145→153: timeframe in cache, skip resampling
            assert mock_resample.call_count == 0

        # Results should be identical
        assert len(result1) == len(result2)
