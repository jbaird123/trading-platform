"""Tests for DataHandler caching and timeframe resampling."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from trading_platform.data.handler import DataHandler, _parse_timeframe_to_minutes


def test_parse_timeframe_minutes() -> None:
    """Test timeframe parsing for minute formats."""
    # Validates: [REQ-DATA-001] Parse minute timeframes
    assert _parse_timeframe_to_minutes("1min") == 1
    assert _parse_timeframe_to_minutes("5MIN") == 5
    assert _parse_timeframe_to_minutes("15T") == 15
    assert _parse_timeframe_to_minutes("1T") == 1


def test_parse_timeframe_hours() -> None:
    """Test timeframe parsing for hour formats."""
    # Validates: [REQ-DATA-002] Parse hour timeframes
    assert _parse_timeframe_to_minutes("1H") == 60
    assert _parse_timeframe_to_minutes("4H") == 240
    assert _parse_timeframe_to_minutes("24h") == 1440


def test_parse_timeframe_days() -> None:
    """Test timeframe parsing for day formats."""
    # Validates: [REQ-DATA-003] Parse day timeframes
    assert _parse_timeframe_to_minutes("1D") == 1440
    assert _parse_timeframe_to_minutes("7d") == 10080


def test_parse_timeframe_weeks() -> None:
    """Test timeframe parsing for week formats."""
    # Validates: [REQ-DATA-004] Parse week timeframes
    assert _parse_timeframe_to_minutes("1W") == 10080
    assert _parse_timeframe_to_minutes("2w") == 20160


def test_parse_timeframe_invalid() -> None:
    """Test invalid timeframe raises ValueError."""
    # Validates: [REQ-DATA-005] Reject invalid timeframe formats
    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("invalid")

    with pytest.raises(ValueError, match="Invalid timeframe format"):
        _parse_timeframe_to_minutes("123")


def test_get_cached_timeframes(tmp_path: Path) -> None:
    """Test get_cached_timeframes returns list of cached timeframes."""
    # Validates: [REQ-DATA-006] Return list of cached timeframes
    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # Initially should have base timeframe
        cached = handler.get_cached_timeframes()
        assert "1min" in cached

        # Request new timeframe
        handler.get_data(timeframe="1H")

        # Should now have both
        cached = handler.get_cached_timeframes()
        assert "1min" in cached
        assert "1h" in cached  # Normalized to lowercase


def test_clear_cache_keep_base(tmp_path: Path) -> None:
    """Test clear_cache with keep_base=True preserves raw data."""
    # Validates: [REQ-DATA-007] clear_cache keeps base when requested
    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # Create cached timeframe
        handler.get_data(timeframe="1H")
        assert len(handler.get_cached_timeframes()) == 2

        # Clear cache keeping base
        handler.clear_cache(keep_base=True)

        # Should only have base
        cached = handler.get_cached_timeframes()
        assert len(cached) == 1
        assert "1min" in cached


def test_clear_cache_full(tmp_path: Path) -> None:
    """Test clear_cache with keep_base=False clears everything."""
    # Validates: [REQ-DATA-008] clear_cache removes all when requested
    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # Clear completely
        handler.clear_cache(keep_base=False)

        assert len(handler.get_cached_timeframes()) == 0


def test_rmm_context_caching(tmp_path: Path) -> None:
    """Test get_rmm_context and set_rmm_context cache RMM results."""
    # Validates: [REQ-DATA-009] RMM context caching
    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        rmm_config = {"timeframe": "1D", "regimes": []}
        timeframe = "1D"

        # Initially no cache
        assert handler.get_rmm_context(rmm_config, timeframe) is None

        # Set cache
        rmm_context = {"test_timestamp": {"label": "trend_up"}}
        handler.set_rmm_context(rmm_config, timeframe, rmm_context)

        # Should be cached now
        cached = handler.get_rmm_context(rmm_config, timeframe)
        assert cached == rmm_context


def test_find_best_resample_source_fallback_edge_case(tmp_path: Path) -> None:
    """Test _find_best_resample_source with invalid cached timeframes."""
    # Validates: [REQ-DATA-010] Handle invalid cached timeframes gracefully
    from unittest.mock import patch

    import pandas as pd

    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        from trading_platform.data.handler import DataHandler

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # Manually add invalid cached timeframe to trigger ValueError path
        handler._cache["invalid_tf"] = raw_data.copy()

        # Should still work, falling back to raw data
        result = handler.get_data(timeframe="1H")
        assert len(result) > 0


def test_get_data_with_date_filtering(tmp_path: Path) -> None:
    """Test get_data applies start/end date filtering correctly."""
    # Validates: [REQ-DATA-011] Filter data by date range
    from unittest.mock import patch

    import pandas as pd

    raw_data = pd.DataFrame(
        {
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "close": [1.05] * 10,
            "volume": [100] * 10,
        },
        index=pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        from trading_platform.data.handler import DataHandler

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # Test start filter
        result = handler.get_data(start="2024-01-05")
        assert len(result) == 6  # Days 5-10

        # Test end filter
        result = handler.get_data(end="2024-01-03")
        assert len(result) == 3  # Days 1-3

        # Test both
        result = handler.get_data(start="2024-01-03", end="2024-01-07")
        assert len(result) == 5  # Days 3-7


def test_find_best_resample_source_uses_raw_data_fallback(tmp_path: Path) -> None:
    """Test _find_best_resample_source falls back to raw data when no match."""
    # Validates: [REQ-DATA-012] Fallback to raw data when no suitable cache
    from unittest.mock import patch

    import pandas as pd

    raw_data = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.05, 2.05],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC"),
    )

    with patch("trading_platform.data.handler.load_instrument_data") as mock_load:
        mock_load.return_value = (raw_data, [])

        from trading_platform.data.handler import DataHandler

        handler = DataHandler(symbol="TEST", data_root=tmp_path)

        # Request timeframe with no suitable cached source (e.g., 7min from 1min base)
        # 7min doesn't evenly divide from anything we have cached
        handler._cache.clear()
        handler._cache["5min"] = raw_data.copy()  # 7 doesn't divide from 5

        # Should fall back to raw data
        result = handler._find_best_resample_source("7min")
        # Fallback line 199 should execute, returning _raw_data
        assert result is handler._raw_data
