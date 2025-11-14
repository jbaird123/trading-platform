"""Tests for the data resampling utility.

This module tests the multi-timeframe resampling functionality used by
the feature engine to compute higher-timeframe contextual features.
"""

from __future__ import annotations

import pandas as pd
import pytest
from trading_platform.data.resample import resample_data


def test_resample_data_correctly_aggregates_ohlc():
    """Test that resample_data correctly aggregates OHLC data.

    Build a 15-minute DataFrame covering 1 hour with deterministic OHLCV
    values, resample to 1H, and verify the output is a single row with
    correct aggregations.
    """
    # Create 4 rows of 15-minute data (covering 1 hour)
    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=4, freq="15min")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [100.5, 101.8, 102.9, 103.5],
            "low": [99.5, 100.2, 101.1, 102.2],
            "close": [100.2, 101.5, 102.5, 103.2],
            "volume": [1000.0, 1500.0, 1200.0, 1800.0],
        },
        index=timestamps,
    )

    result = resample_data(df, rule="1H")

    # Should produce a single row
    assert len(result) == 1
    assert result.index[0] == timestamps[0]

    # Verify aggregations
    row = result.iloc[0]
    assert row["open"] == 100.0  # first open
    assert row["high"] == 103.5  # max high
    assert row["low"] == 99.5  # min low
    assert row["close"] == 103.2  # last close
    assert row["volume"] == 5500.0  # sum of volume


def test_resample_data_handles_multiple_bins_and_partial_tail():
    """Test that resample_data handles multiple bins and drops partial tail.

    Create 15-minute data covering 2.5 hours (10 bars), resample to 1H,
    and verify we get 2 rows (2 complete hours).
    The partial final row is dropped by .dropna().
    """
    # Create 10 rows of 15-minute data (2.5 hours)
    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=10, freq="15min")
    df = pd.DataFrame(
        {
            "open": list(range(100, 110)),
            "high": list(range(101, 111)),
            "low": list(range(99, 109)),
            "close": list(range(100, 110)),
            "volume": [1000.0] * 10,
        },
        index=timestamps,
    )

    result = resample_data(df, rule="1H")

    # Should have 2 rows: 2 complete hours, partial hour dropped
    assert len(result) == 2
    assert result.index[0] == timestamps[0]
    assert result.index[1] == timestamps[4]

    # First hour (bars 0-3)
    row0 = result.iloc[0]
    assert row0["open"] == 100  # first open
    assert row0["high"] == 104  # max high in first 4 bars
    assert row0["low"] == 99  # min low in first 4 bars
    assert row0["close"] == 103  # last close in first 4 bars
    assert row0["volume"] == 4000.0  # sum of first 4 bars

    # Second hour (bars 4-7)
    row1 = result.iloc[1]
    assert row1["open"] == 104
    assert row1["high"] == 108
    assert row1["low"] == 103
    assert row1["close"] == 107
    assert row1["volume"] == 4000.0


def test_resample_data_preserves_timezone_and_index_type():
    """Test that resample_data preserves timezone info and DatetimeIndex type.

    Start with a UTC-indexed DataFrame and verify the output retains
    timezone awareness.
    """
    # Create UTC-aware timestamps
    timestamps = pd.date_range(
        start="2024-01-01 00:00:00", periods=4, freq="15min", tz="UTC"
    )
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [100.5, 101.5, 102.5, 103.5],
            "low": [99.5, 100.5, 101.5, 102.5],
            "close": [100.2, 101.2, 102.2, 103.2],
            "volume": [1000.0, 1000.0, 1000.0, 1000.0],
        },
        index=timestamps,
    )

    result = resample_data(df, rule="1H")

    # Verify index type
    assert isinstance(result.index, pd.DatetimeIndex)

    # Verify timezone is preserved
    assert result.index.tz is not None
    assert str(result.index.tz) == "UTC"


def test_resample_data_errors_on_non_datetime_index():
    """Test that resample_data raises TypeError for non-DatetimeIndex.

    Pass a DataFrame with a RangeIndex and verify TypeError is raised.
    """
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [100.5, 101.5, 102.5, 103.5],
            "low": [99.5, 100.5, 101.5, 102.5],
            "close": [100.2, 101.2, 102.2, 103.2],
            "volume": [1000.0, 1000.0, 1000.0, 1000.0],
        }
    )

    with pytest.raises(TypeError, match="DatetimeIndex"):
        resample_data(df, rule="1H")


def test_resample_data_errors_on_invalid_timeframe_rule():
    """Test that resample_data raises ValueError for invalid rule.

    Pass an invalid resampling rule (e.g., 'INVALID') and verify
    ValueError is raised.
    """
    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=4, freq="15min")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [100.5, 101.5, 102.5, 103.5],
            "low": [99.5, 100.5, 101.5, 102.5],
            "close": [100.2, 101.2, 102.2, 103.2],
            "volume": [1000.0, 1000.0, 1000.0, 1000.0],
        },
        index=timestamps,
    )

    with pytest.raises(ValueError, match="Invalid frequency"):
        resample_data(df, rule="INVALID")


def test_resample_data_returns_empty_for_sparse_resampling():
    """Test that resample_data returns empty DataFrame for all-NaN input.

    Create a DataFrame that contains no actual data (all NaN). Resampling
    should return an empty DataFrame without raising warnings.
    """
    import numpy as np

    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=4, freq="1h")
    df = pd.DataFrame(
        {
            "open": [np.nan, np.nan, np.nan, np.nan],
            "high": [np.nan, np.nan, np.nan, np.nan],
            "low": [np.nan, np.nan, np.nan, np.nan],
            "close": [np.nan, np.nan, np.nan, np.nan],
            "volume": [np.nan, np.nan, np.nan, np.nan],
        },
        index=timestamps,
    )

    result = resample_data(df, rule="1D")

    assert result.empty
