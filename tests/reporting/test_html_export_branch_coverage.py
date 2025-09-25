"""Test coverage for html_export.py missing branch coverage."""

from datetime import datetime

import pandas as pd
from trading_platform.reporting.html_export import _spark_svg


def test_spark_svg_no_overlays():
    """Test _spark_svg with no overlays (branch 55->63)."""
    # Create simple price series as list of tuples
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    entry_exit_ts = [(dates[0].to_pydatetime(), dates[2].to_pydatetime())]

    # Test with empty overlays dict (should skip overlay processing)
    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result
    # The CSS includes overlay style but no overlay elements should be present
    assert "class='ov'" not in result  # No overlay elements should be present


def test_spark_svg_missing_entry_timestamp():
    """Test _spark_svg when entry timestamp not found in xs_map (branch 69->73)."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    # Use a timestamp that won't be in xs_map (different date)
    missing_entry_date = datetime(2023, 12, 31)  # Not in price series
    entry_exit_ts = [(missing_entry_date, dates[1].to_pydatetime())]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result
    # Should have exit marker but no entry marker due to None check


def test_spark_svg_missing_exit_timestamp():
    """Test _spark_svg when exit timestamp not found in xs_map (branch 73->66)."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    # Use a timestamp that won't be in xs_map for exit
    missing_exit_date = datetime(2023, 12, 31)  # Not in price series
    entry_exit_ts = [(dates[0].to_pydatetime(), missing_exit_date)]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result
    # Should have entry marker but no exit marker due to None check


def test_spark_svg_both_timestamps_missing():
    """Test _spark_svg when both entry and exit timestamps are missing."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    # Both timestamps not in price series
    missing_entry = datetime(2023, 12, 30)
    missing_exit = datetime(2023, 12, 31)
    entry_exit_ts = [(missing_entry, missing_exit)]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result
    # Should have neither entry nor exit markers
    # Both if conditions should be false, hitting the missing branches


def test_spark_svg_empty_entry_exit_list():
    """Test _spark_svg with empty entry_exit_ts list."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    # Empty entry/exit list - should skip the marker loop entirely
    result = _spark_svg(prices, {}, [])
    assert "<svg" in result
    # CSS includes marker styles but no marker elements should be present
    assert "class='mk'" not in result  # No marker elements should be present
    assert "class='mk2'" not in result
