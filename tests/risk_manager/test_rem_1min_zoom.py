"""
Tests for REM 1-minute resolution zoom integration.

These tests verify that RiskExitManager:
- Detects trailing stop ambiguity on primary timeframe bars
- Requests 1-minute data from DataHandler when ambiguous
- Processes 1-minute bars and returns correct exit signal
- Does NOT zoom to 1-minute when no ambiguity detected
- Properly integrates fixed stop + TP ambiguity detection
"""

from unittest.mock import Mock

import pandas as pd
import pytest
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager


@pytest.fixture
def mock_instrument():
    """Create mock instrument with EUR/USD parameters."""
    return {"pip_location": 0.0001, "symbol": "EUR_USD"}


@pytest.fixture
def mock_data_handler():
    """Create mock DataHandler."""
    mock = Mock()
    return mock


def test_rem_detects_trailing_stop_ambiguity_and_zooms_to_1min(
    mock_instrument, mock_data_handler
):
    """Test that REM detects ambiguity and zooms to 1-minute resolution."""
    # Long position at 1.0600 with 20-pip trailing stop
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="long",
        size=1.0,
        mfe_currency=0.0,  # No favorable movement yet
    )

    # Current hourly bar where trailing stop is ambiguous
    # Low = 1.0575, trailing stop at 1.0580 (entry - 20 pips)
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0600,
            "high": 1.0605,
            "low": 1.0575,  # Below stop level
            "close": 1.0590,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    # Mock 1-minute bars where stop is NOT hit
    bars_1min = pd.DataFrame(
        [
            {"open": 1.0600, "high": 1.0605, "low": 1.0590, "close": 1.0595}
            for _ in range(60)
        ]
    )
    bars_1min.index = pd.date_range(
        "2023-01-01 11:00:00", periods=60, freq="1min", tz="UTC"
    )
    mock_data_handler.get_data.return_value = bars_1min

    # Configure REM with 20-pip trailing stop
    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 50},
        "trailing_stop": {
            "distance": {"type": "fixed_pips", "pips": 20},
        },
    }

    rem = RiskExitManager(config=config, instrument=mock_instrument)

    # Check exits - should zoom to 1-minute and find no exit
    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Verify DataHandler was called for 1-minute data
    # Verify get_data was called with correct timeframe and time range
    mock_data_handler.get_data.assert_called_once()
    call_args = mock_data_handler.get_data.call_args
    assert call_args.kwargs["timeframe"] == "1min"

    # Should return None (no exit) because 1-minute resolution shows no hit
    assert result is None


def test_rem_zooms_and_detects_trailing_stop_hit_on_1min_bar(
    mock_instrument, mock_data_handler
):
    """Test that REM zooms to 1-min and correctly detects stop hit."""
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="long",
        size=1.0,
        mfe_currency=0.0,
    )

    # Ambiguous hourly bar
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0600,
            "high": 1.0605,
            "low": 1.0575,
            "close": 1.0585,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    # Mock 1-minute bars where stop IS hit on minute 30
    bars_1min_data = []
    for i in range(60):
        if i < 30:
            # Keep price at or below entry so stop doesn't trail
            bars_1min_data.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0590, "close": 1.0600}
            )
        elif i == 30:
            # Stop hit here at 1.0580 (entry - 20 pips)
            bars_1min_data.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0575, "close": 1.0580}
            )
        else:
            bars_1min_data.append(
                {"open": 1.0580, "high": 1.0585, "low": 1.0575, "close": 1.0580}
            )

    bars_1min = pd.DataFrame(bars_1min_data)
    bars_1min.index = pd.date_range(
        "2023-01-01 11:00:00", periods=60, freq="1min", tz="UTC"
    )
    mock_data_handler.get_data.return_value = bars_1min

    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 50},
        "trailing_stop": {
            "distance": {"type": "fixed_pips", "pips": 20},
        },
    }
    rem = RiskExitManager(config=config, instrument=mock_instrument)

    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Should detect exit at stop level
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == 1.0580


def test_rem_does_not_zoom_when_no_ambiguity(mock_instrument, mock_data_handler):
    """Test that REM does NOT zoom to 1-min when no ambiguity exists."""
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="long",
        size=1.0,
        mfe_currency=0.0,
    )

    # Non-ambiguous bar - low well above potential trailing stop
    # Bar high (1.0610) creates potential peak, potential stop = 1.0590
    # Bar low (1.0595) is above potential stop (1.0590), so not ambiguous
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0600,
            "high": 1.0610,
            "low": 1.0595,  # Above potential trailing stop at 1.0590
            "close": 1.0605,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 50},
        "trailing_stop": {
            "distance": {"type": "fixed_pips", "pips": 20},
        },
    }
    rem = RiskExitManager(config=config, instrument=mock_instrument)

    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Should NOT call DataHandler (no zoom needed)
    mock_data_handler.get_data.assert_not_called()

    # Should return None (no exit)
    assert result is None


def test_rem_trailing_stop_with_favorable_movement_zooms_correctly(
    mock_instrument, mock_data_handler
):
    """Test that REM correctly handles trailing stop with favorable movement."""
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="long",
        size=1.0,
        mfe_currency=0.0040 * 1.0,  # Favorable movement of 40 pips
    )

    # Ambiguous bar - trailing stop should be at 1.0620 (peak 1.0640 - 20 pips)
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0635,
            "high": 1.0640,
            "low": 1.0615,  # Hits trailed stop
            "close": 1.0625,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    # 1-minute bars showing gradual rally to peak, then retrace
    bars_1min_data = []
    for i in range(60):
        if i < 20:
            # Rally to peak
            bars_1min_data.append(
                {"open": 1.0635, "high": 1.0640, "low": 1.0630, "close": 1.0635}
            )
        elif i == 30:
            # Retrace hits trailed stop at 1.0620
            bars_1min_data.append(
                {"open": 1.0635, "high": 1.0635, "low": 1.0615, "close": 1.0620}
            )
        else:
            bars_1min_data.append(
                {"open": 1.0625, "high": 1.0630, "low": 1.0620, "close": 1.0625}
            )

    bars_1min = pd.DataFrame(bars_1min_data)
    bars_1min.index = pd.date_range(
        "2023-01-01 11:00:00", periods=60, freq="1min", tz="UTC"
    )
    mock_data_handler.get_data.return_value = bars_1min

    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 50},
        "trailing_stop": {
            "distance": {"type": "fixed_pips", "pips": 20},
        },
    }
    rem = RiskExitManager(config=config, instrument=mock_instrument)

    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Should detect exit at trailed stop level
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == 1.0620


def test_rem_short_position_trailing_stop_zoom(mock_instrument, mock_data_handler):
    """Test 1-minute zoom for short position with trailing stop."""
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="short",
        size=1.0,
        mfe_currency=0.0040 * 1.0,  # Favorable movement of 40 pips
    )

    # Ambiguous bar - trailing stop at 1.0580 (trough 1.0560 + 20 pips)
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0565,
            "high": 1.0585,  # Hits trailed stop
            "low": 1.0560,
            "close": 1.0575,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    # 1-minute bars showing drop to trough, then rally
    bars_1min_data = []
    for i in range(60):
        if i < 20:
            # Drop to trough
            bars_1min_data.append(
                {"open": 1.0565, "high": 1.0570, "low": 1.0560, "close": 1.0565}
            )
        elif i == 30:
            # Rally hits trailed stop
            bars_1min_data.append(
                {"open": 1.0565, "high": 1.0585, "low": 1.0565, "close": 1.0575}
            )
        else:
            bars_1min_data.append(
                {"open": 1.0575, "high": 1.0580, "low": 1.0570, "close": 1.0575}
            )

    bars_1min = pd.DataFrame(bars_1min_data)
    bars_1min.index = pd.date_range(
        "2023-01-01 11:00:00", periods=60, freq="1min", tz="UTC"
    )
    mock_data_handler.get_data.return_value = bars_1min

    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 50},
        "trailing_stop": {
            "distance": {"type": "fixed_pips", "pips": 20},
        },
    }
    rem = RiskExitManager(config=config, instrument=mock_instrument)

    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Should detect exit at trailed stop level
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == 1.0580


def test_rem_fixed_stop_and_tp_both_ambiguous_zooms_to_1min(
    mock_instrument, mock_data_handler
):
    """Test that REM zooms when both fixed stop and TP are in bar's range."""
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="long",
        size=1.0,
        mfe_currency=0.0,
    )

    # Ambiguous bar - both stop (1.0580) and TP (1.0650) are in range
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0600,
            "high": 1.0655,  # Above TP
            "low": 1.0575,  # Below stop
            "close": 1.0620,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    # 1-minute bars: stop hit first on bar 15
    bars_1min_data = []
    for i in range(60):
        if i < 15:
            bars_1min_data.append(
                {"open": 1.0600, "high": 1.0605, "low": 1.0595, "close": 1.0600}
            )
        elif i == 15:
            # Stop hit first
            bars_1min_data.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0575, "close": 1.0580}
            )
        else:
            bars_1min_data.append(
                {"open": 1.0620, "high": 1.0655, "low": 1.0615, "close": 1.0630}
            )

    bars_1min = pd.DataFrame(bars_1min_data)
    bars_1min.index = pd.date_range(
        "2023-01-01 11:00:00", periods=60, freq="1min", tz="UTC"
    )
    mock_data_handler.get_data.return_value = bars_1min

    # Configure with both fixed stop and TP
    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 20},
        "take_profit": {"type": "fixed_pips", "pips": 50},
    }
    rem = RiskExitManager(config=config, instrument=mock_instrument)

    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Should zoom and detect stop hit first
    mock_data_handler.get_data.assert_called_once()
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == 1.0580


def test_rem_fixed_stop_tp_ambiguous_tp_hits_first(mock_instrument, mock_data_handler):
    """Test that REM correctly detects TP hit first when both are ambiguous."""
    position = Position(
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2023-01-01 10:00:00", tz="UTC"),
        entry_price=1.0600,
        entry_mid_price=1.0600,
        side="long",
        size=1.0,
        mfe_currency=0.0,
    )

    # Ambiguous bar
    current_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
            "open": 1.0600,
            "high": 1.0655,
            "low": 1.0575,
            "close": 1.0640,
        },
        name=pd.Timestamp("2023-01-01 11:00:00", tz="UTC"),
    )

    # 1-minute bars: TP hit first on bar 20
    bars_1min_data = []
    for i in range(60):
        if i < 20:
            # Rally to TP
            bars_1min_data.append(
                {
                    "open": 1.0600 + i * 0.0002,
                    "high": 1.0610 + i * 0.0002,
                    "low": 1.0595 + i * 0.0002,
                    "close": 1.0605 + i * 0.0002,
                }
            )
        elif i == 20:
            # TP hit
            bars_1min_data.append(
                {"open": 1.0645, "high": 1.0655, "low": 1.0640, "close": 1.0650}
            )
        else:
            bars_1min_data.append(
                {"open": 1.0640, "high": 1.0645, "low": 1.0635, "close": 1.0640}
            )

    bars_1min = pd.DataFrame(bars_1min_data)
    bars_1min.index = pd.date_range(
        "2023-01-01 11:00:00", periods=60, freq="1min", tz="UTC"
    )
    mock_data_handler.get_data.return_value = bars_1min

    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 20},
        "take_profit": {"type": "fixed_pips", "pips": 50},
    }
    rem = RiskExitManager(config=config, instrument=mock_instrument)

    result = rem.check_exits(position, current_bar, data_handler=mock_data_handler)

    # Should detect TP hit first
    assert result is not None
    assert result["reason"] == "take-profit"
    assert result["exit_price"] == 1.0650
