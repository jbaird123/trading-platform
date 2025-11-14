"""Tests for timeframe comparison utility."""

import pytest
from trading_platform.core.timeframes import compare_timeframes


def test_compare_timeframes_less_than() -> None:
    """Test that compare_timeframes returns negative for smaller timeframe."""
    assert compare_timeframes("1min", "1H") < 0
    assert compare_timeframes("5min", "1D") < 0
    assert compare_timeframes("15min", "4H") < 0


def test_compare_timeframes_greater_than() -> None:
    """Test that compare_timeframes returns positive for larger timeframe."""
    assert compare_timeframes("1H", "1min") > 0
    assert compare_timeframes("1D", "5min") > 0
    assert compare_timeframes("4H", "15min") > 0


def test_compare_timeframes_equal() -> None:
    """Test that compare_timeframes returns 0 for equal timeframes."""
    assert compare_timeframes("1min", "1min") == 0
    assert compare_timeframes("15min", "15min") == 0
    assert compare_timeframes("1H", "1H") == 0
    assert compare_timeframes("1D", "1D") == 0


def test_compare_timeframes_all_ordering() -> None:
    """Test complete ordering: 1min < 5min < 15min < 1H < 4H < 1D."""
    timeframes = ["1min", "5min", "15min", "1H", "4H", "1D"]

    for i in range(len(timeframes)):
        for j in range(i + 1, len(timeframes)):
            # timeframes[i] should be < timeframes[j]
            assert compare_timeframes(timeframes[i], timeframes[j]) < 0
            # timeframes[j] should be > timeframes[i]
            assert compare_timeframes(timeframes[j], timeframes[i]) > 0


def test_compare_timeframes_unrecognized_timeframe() -> None:
    """Test that compare_timeframes raises ValueError for unrecognized timeframe."""
    with pytest.raises(ValueError) as exc_info:
        compare_timeframes("invalid", "1H")

    assert "unrecognized timeframe" in str(exc_info.value).lower()
    assert "invalid" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        compare_timeframes("1H", "2h")

    assert "unrecognized timeframe" in str(exc_info.value).lower()
    assert "2h" in str(exc_info.value)
