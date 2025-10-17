"""
Tests for DataHandler 1-minute bar retrieval for specific hours.

These tests verify that the DataHandler can correctly retrieve 1-minute bars
for a specific hour from the already-cached 1-minute base data.
"""

import pandas as pd
import pytest

from src.trading_platform.data.handler import DataHandler


@pytest.fixture
def mock_data_root(tmp_path):
    """Create a temporary data directory with test data."""
    # Follow expected directory structure: data_root/full/eurusd/
    # (normalize_symbol removes _ and converts to lowercase)
    data_dir = tmp_path / "full" / "eurusd"
    data_dir.mkdir(parents=True)

    # Create test 1-minute data covering multiple hours
    timestamps = pd.date_range(
        start="2023-01-01 00:00:00", end="2023-01-01 03:00:00", freq="1min", tz="UTC"
    )

    # Convert timestamps to strings for CSV format
    data = pd.DataFrame(
        {
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S+00:00"),
            "open": range(len(timestamps)),
            "high": range(1, len(timestamps) + 1),
            "low": range(len(timestamps)),
            "close": range(len(timestamps)),
            "volume": [100] * len(timestamps),
        }
    )

    # Save to CSV (loader expects CSV files)
    data_file = data_dir / "eurusd_1min.csv"
    data.to_csv(data_file, index=False)

    return tmp_path


def test_get_1min_bars_for_hour_returns_correct_shape(mock_data_root):
    """Test that get_1min_bars_for_hour returns up to 60 bars for a full hour."""
    handler = DataHandler("EUR_USD", mock_data_root)

    # Get bars for the first hour (00:00-01:00)
    timestamp = pd.Timestamp("2023-01-01 00:30:00", tz="UTC")
    bars = handler.get_1min_bars_for_hour(timestamp)

    # Should have 60 bars for a full hour (00:00 to 00:59)
    assert len(bars) == 60
    assert bars.index[0] == pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    assert bars.index[-1] == pd.Timestamp("2023-01-01 00:59:00", tz="UTC")


def test_get_1min_bars_for_hour_with_timestamp_at_hour_start(mock_data_root):
    """Test retrieval when timestamp is exactly at hour start."""
    handler = DataHandler("EUR_USD", mock_data_root)

    timestamp = pd.Timestamp("2023-01-01 01:00:00", tz="UTC")
    bars = handler.get_1min_bars_for_hour(timestamp)

    # Should get bars from 01:00 to 01:59
    assert len(bars) == 60
    assert bars.index[0] == pd.Timestamp("2023-01-01 01:00:00", tz="UTC")
    assert bars.index[-1] == pd.Timestamp("2023-01-01 01:59:00", tz="UTC")


def test_get_1min_bars_for_hour_with_timestamp_at_hour_end(mock_data_root):
    """Test retrieval when timestamp is at the end of an hour."""
    handler = DataHandler("EUR_USD", mock_data_root)

    timestamp = pd.Timestamp("2023-01-01 00:59:00", tz="UTC")
    bars = handler.get_1min_bars_for_hour(timestamp)

    # Should get bars from 00:00 to 00:59 (the hour containing 00:59)
    assert len(bars) == 60
    assert bars.index[0] == pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    assert bars.index[-1] == pd.Timestamp("2023-01-01 00:59:00", tz="UTC")


def test_get_1min_bars_for_hour_returns_correct_columns(mock_data_root):
    """Test that returned DataFrame has correct OHLCV columns."""
    handler = DataHandler("EUR_USD", mock_data_root)

    timestamp = pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    bars = handler.get_1min_bars_for_hour(timestamp)

    expected_columns = ["open", "high", "low", "close", "volume"]
    assert list(bars.columns) == expected_columns


def test_get_1min_bars_for_hour_with_missing_data(mock_data_root):
    """Test handling when some minutes are missing (market gaps)."""
    # Create data with gaps
    data_dir = mock_data_root / "full" / "gbpusd"
    data_dir.mkdir(parents=True)

    # Only create data for first 30 minutes of an hour
    timestamps = pd.date_range(
        start="2023-01-01 00:00:00", end="2023-01-01 00:29:00", freq="1min", tz="UTC"
    )

    data = pd.DataFrame(
        {
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S+00:00"),
            "open": range(len(timestamps)),
            "high": range(1, len(timestamps) + 1),
            "low": range(len(timestamps)),
            "close": range(len(timestamps)),
            "volume": [100] * len(timestamps),
        }
    )

    data_file = data_dir / "gbpusd_1min.csv"
    data.to_csv(data_file, index=False)

    handler_with_gaps = DataHandler("GBP_USD", mock_data_root)
    timestamp = pd.Timestamp("2023-01-01 00:15:00", tz="UTC")
    bars = handler_with_gaps.get_1min_bars_for_hour(timestamp)

    # Should return only the available data (30 bars)
    assert len(bars) == 30
    assert bars.index[0] == pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    assert bars.index[-1] == pd.Timestamp("2023-01-01 00:29:00", tz="UTC")


def test_get_1min_bars_for_hour_with_partial_hour_at_end(mock_data_root):
    """Test handling when requesting the last partial hour in dataset."""
    handler = DataHandler("EUR_USD", mock_data_root)

    # Request the last hour which only has data until 03:00
    timestamp = pd.Timestamp("2023-01-01 03:00:00", tz="UTC")
    bars = handler.get_1min_bars_for_hour(timestamp)

    # Should return only 1 bar (03:00:00)
    assert len(bars) == 1
    assert bars.index[0] == pd.Timestamp("2023-01-01 03:00:00", tz="UTC")


def test_get_1min_bars_for_hour_uses_cached_data(mock_data_root):
    """Test that no disk reads occur - data is already cached."""
    handler = DataHandler("EUR_USD", mock_data_root)

    # First call - data is already loaded in __init__
    timestamp1 = pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    bars1 = handler.get_1min_bars_for_hour(timestamp1)

    # Check that 1min is in cache
    cached_timeframes = handler.get_cached_timeframes()
    assert "1min" in cached_timeframes

    # Second call - should use cached data
    timestamp2 = pd.Timestamp("2023-01-01 01:00:00", tz="UTC")
    bars2 = handler.get_1min_bars_for_hour(timestamp2)

    # Verify both calls succeeded
    assert len(bars1) == 60
    assert len(bars2) == 60

    # Verify cache still only has base timeframe (no resampling occurred)
    cached_timeframes_after = handler.get_cached_timeframes()
    assert "1min" in cached_timeframes_after


def test_get_1min_bars_for_hour_with_timezone_aware_timestamp(mock_data_root):
    """Test that timezone-aware timestamps are handled correctly."""
    handler = DataHandler("EUR_USD", mock_data_root)

    timestamp = pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    bars = handler.get_1min_bars_for_hour(timestamp)

    # Verify all returned timestamps are timezone-aware UTC
    assert bars.index.tz is not None
    assert str(bars.index.tz) == "UTC"


def test_get_1min_bars_for_hour_consecutive_hours(mock_data_root):
    """Test retrieving bars from consecutive hours returns distinct data."""
    handler = DataHandler("EUR_USD", mock_data_root)

    # Get bars for hour 0
    hour0 = handler.get_1min_bars_for_hour(
        pd.Timestamp("2023-01-01 00:00:00", tz="UTC")
    )

    # Get bars for hour 1
    hour1 = handler.get_1min_bars_for_hour(
        pd.Timestamp("2023-01-01 01:00:00", tz="UTC")
    )

    # Get bars for hour 2
    hour2 = handler.get_1min_bars_for_hour(
        pd.Timestamp("2023-01-01 02:00:00", tz="UTC")
    )

    # Verify they're distinct and sequential
    assert len(hour0) == 60
    assert len(hour1) == 60
    assert len(hour2) == 60

    # Last bar of hour0 should be before first bar of hour1
    assert hour0.index[-1] < hour1.index[0]
    assert hour1.index[-1] < hour2.index[0]

    # Verify data values are different
    assert not hour0["open"].equals(hour1["open"])
    assert not hour1["open"].equals(hour2["open"])
