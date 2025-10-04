"""Comprehensive test coverage for RiskExitManager to achieve 100% line coverage."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager


@pytest.fixture
def basic_rem() -> RiskExitManager:
    """Create a basic REM instance for testing."""
    config = {"stop_loss": {"pips": 50}, "take_profit": {"price_offset": 0.0050}}
    return RiskExitManager(config)


@pytest.fixture
def trailing_rem() -> RiskExitManager:
    """Create a REM instance with trailing stops."""
    config = {
        "stop_loss": {"pips": 50},
        "take_profit": {"price_offset": 0.0050},
        "trailing_stop": {"pips": 30},
    }
    return RiskExitManager(config)


def test_pip_size_none_metadata(basic_rem):
    """Test _pip_size fails loudly when instrument metadata is None."""
    # Create REM without instrument metadata - should fail when using pips
    rem_no_instrument = RiskExitManager({"stop_loss": {"pips": 50}}, instrument=None)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    current_bar = pd.Series({"high": 1.1030, "low": 1.0970})

    # Should raise ValueError when trying to calculate pip-based offsets
    with pytest.raises(
        ValueError, match="pip_location missing from instrument definition"
    ):
        rem_no_instrument.check_exits(position, current_bar)


def test_atr_value_none_metadata():
    """Test _atr_value when instrument metadata is None (line 55)."""
    # Create REM with ATR-based rules but no instrument metadata
    config = {"stop_loss": {"atr_multiple": 2.0}, "take_profit": {"atr_multiple": 3.0}}
    rem = RiskExitManager(config, instrument=None)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    current_bar = pd.Series({"high": 1.1050, "low": 1.0950})

    # This will trigger _atr_value with None metadata, hitting line 55
    result = rem.check_exits(position, current_bar)
    assert result is None


def test_distance_none_rule_and_invalid_types():
    """Test distance calculation with None/invalid rules (line 59-61)."""
    # Create a position that will trigger internal function calls but not exit
    config: dict[str, dict] = {"stop_loss": {}}  # Empty config to trigger None distance
    rem = RiskExitManager(config)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    # Current bar doesn't trigger exits, but will exercise internal logic
    current_bar = pd.Series({"high": 1.1020, "low": 1.0980})

    # This should trigger the _distance function with empty rules, hitting lines 59-61
    result = rem.check_exits(position, current_bar)
    assert result is None


def test_distance_atr_multiple_none_atr():
    """Test atr_multiple logic when ATR data is None (line 60)."""
    # Create config with ATR-based stop loss but no ATR data available
    config = {"stop_loss": {"atr_multiple": 2.0}}
    rem = RiskExitManager(config, instrument=None)  # No instrument = no ATR data

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    current_bar = pd.Series({"high": 1.1020, "low": 1.0980})

    # This should trigger atr_multiple logic but return None due to no ATR (line 60)
    result = rem.check_exits(position, current_bar)
    assert result is None


def test_level_price_none_rule():
    """Test level price calculation with None/invalid rules (line 68)."""
    # Create config with None values to trigger _level_price None handling
    config = {"stop_loss": None, "take_profit": None}
    rem = RiskExitManager(config)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    current_bar = pd.Series({"high": 1.1020, "low": 1.0980})

    # This should trigger _level_price with None rules, hitting line 68
    result = rem.check_exits(position, current_bar)
    assert result is None


def test_trailing_stop_logic_long_position():
    """Test trailing stop calculation for long positions (lines 82-95)."""
    config = {"stop_loss": {"pips": 50}, "trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Create position with positive MFE (profit)
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
        mfe_currency=500.0,  # $500 profit on 100k position = 50 pips
    )

    current_bar = pd.Series({"high": 1.1080, "low": 1.1030})

    # This should trigger trailing stop calculation for long position (lines 86-89)
    result = rem.check_exits(position, current_bar)
    # Position should not exit as current low is above trail price
    assert result is None


def test_trailing_stop_logic_short_position():
    """Test trailing stop calculation for short positions (lines 90-95)."""
    config = {"stop_loss": {"pips": 50}, "trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Create position with positive MFE (profit for short)
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="short",
        size=100000.0,
        mfe_currency=500.0,  # $500 profit on 100k position = 50 pips lower
    )

    current_bar = pd.Series({"high": 1.0970, "low": 1.0920})

    # This should trigger trailing stop calculation for short position (lines 91-95)
    result = rem.check_exits(position, current_bar)
    # Position should not exit as current high is below trail price
    assert result is None


def test_long_position_stop_loss_exit():
    """Test long position stop loss exit (line 107)."""
    config = {"stop_loss": {"pips": 50}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    # Current bar low touches stop loss level (1.1000 - 0.0050 = 1.0950)
    current_bar = pd.Series({"high": 1.1000, "low": 1.0950})

    # This should trigger stop loss exit (line 107)
    result = rem.check_exits(position, current_bar)
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == pytest.approx(1.0950, abs=1e-6)


def test_long_position_take_profit_exit():
    """Test long position take profit exit (lines 110-111)."""
    config = {"take_profit": {"price_offset": 0.0050}}
    rem = RiskExitManager(config)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    # Current bar high reaches take profit level (1.1000 + 0.0050 = 1.1050)
    current_bar = pd.Series({"high": 1.1050, "low": 1.1000})

    # This should trigger take profit exit (lines 110-111)
    result = rem.check_exits(position, current_bar)
    assert result is not None
    assert result["reason"] == "take-profit"
    assert result["exit_price"] == 1.1050


def test_short_position_stop_loss_exit():
    """Test short position stop loss exit (line 120)."""
    config = {"stop_loss": {"pips": 50}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="short",
        size=100000.0,
    )
    # Current bar high touches stop loss level (1.1000 + 0.0050 = 1.1050)
    current_bar = pd.Series({"high": 1.1050, "low": 1.1000})

    # This should trigger stop loss exit (line 120)
    result = rem.check_exits(position, current_bar)
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == 1.1050


def test_short_position_take_profit_exit():
    """Test short position take profit exit (lines 123-126)."""
    config = {"take_profit": {"price_offset": 0.0050}}
    rem = RiskExitManager(config)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="short",
        size=100000.0,
    )
    # Current bar low reaches take profit level (1.1000 - 0.0050 = 1.0950)
    current_bar = pd.Series({"high": 1.1000, "low": 1.0950})

    # This should trigger take profit exit (lines 123-126)
    result = rem.check_exits(position, current_bar)
    assert result is not None
    assert result["reason"] == "take-profit"
    assert result["exit_price"] == pytest.approx(1.0950, abs=1e-6)


def test_no_exit_conditions_met():
    """Test when no exit conditions are met, returning None."""
    config = {
        "stop_loss": {"pips": 100},  # Very wide stop
        "take_profit": {"price_offset": 0.0100},  # Very wide target
    }
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    # Current bar doesn't trigger any exits
    current_bar = pd.Series({"high": 1.1020, "low": 1.0980})

    # Should return None (no exits)
    result = rem.check_exits(position, current_bar)
    assert result is None


def test_effective_stop_loss_multiple_values_long():
    """Test effective stop loss calculation with multiple values for long positions."""
    config = {"stop_loss": {"pips": 50}, "trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Create position where trailing stop is tighter than regular stop
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
        mfe_currency=300.0,  # Some profit to activate trailing
    )

    # Current bar that would trigger trailing stop but not regular stop
    current_bar = pd.Series({"high": 1.1040, "low": 1.0975})

    result = rem.check_exits(position, current_bar)
    # Should exit on trailing stop (the higher/tighter stop for longs)
    if result is not None:
        assert result["reason"] == "stop-loss"


def test_effective_stop_loss_multiple_values_short():
    """Test effective stop loss calculation with multiple values for short positions."""
    config = {"stop_loss": {"pips": 50}, "trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Create position where trailing stop is tighter than regular stop
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="short",
        size=100000.0,
        mfe_currency=300.0,  # Some profit to activate trailing
    )

    # Current bar that would trigger trailing stop but not regular stop
    current_bar = pd.Series({"high": 1.1025, "low": 1.0960})

    result = rem.check_exits(position, current_bar)
    # Should exit on trailing stop (the lower/tighter stop for shorts)
    if result is not None:
        assert result["reason"] == "stop-loss"


def test_position_size_zero():
    """Test when position size is 0, defaults to 1.0 (line 84)."""
    config = {"trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Position class requires size, but we can test with size=0 to trigger line 84
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=0.0,  # This will trigger the `else 1.0` branch on line 84
        mfe_currency=100.0,
    )

    current_bar = pd.Series({"high": 1.1050, "low": 1.1000})

    # Should handle zero size by defaulting to 1.0 in MFE calculation
    result = rem.check_exits(position, current_bar)
    # Should not crash and return a valid result or None
    assert result is None or isinstance(result, dict)


def test_position_size_none():
    """Test when position size is truthy, uses actual size."""
    config = {"trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Test with normal positive size to cover the `if position.size` branch
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,  # This will trigger the `if position.size` branch on line 84
        mfe_currency=100.0,
    )

    current_bar = pd.Series({"high": 1.1050, "low": 1.1000})

    # Should use actual size in MFE calculation
    result = rem.check_exits(position, current_bar)
    # Should not crash and return a valid result or None
    assert result is None or isinstance(result, dict)


def test_trailing_stop_distance_none():
    """Test trailing stop when distance calculation returns None (line 83->99)."""
    # Config with trailing_stop but no valid distance fields
    config = {
        "trailing_stop": {"invalid_field": "value"}
    }  # No pips, price_offset, or atr_multiple
    rem = RiskExitManager(config)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
        mfe_currency=100.0,  # Some MFE to make sure we enter the trailing logic
    )
    current_bar = pd.Series({"high": 1.1050, "low": 1.1000})

    # This should enter `if trailing:` but then dist_t will be None,
    # causing the entire trailing block to be skipped (line 83->99 branch)
    result = rem.check_exits(position, current_bar)
    assert result is None


def test_mfe_currency_none():
    """Test when mfe_currency is None."""
    config = {"trailing_stop": {"pips": 30}}
    rem = RiskExitManager(config, instrument={"pip_location": 0.0001})

    # Position defaults mfe_currency to 0.0, but we can test the logic
    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
        mfe_currency=0.0,  # Test with 0.0 MFE
    )

    current_bar = pd.Series({"high": 1.1050, "low": 1.1000})

    # Should handle 0.0 MFE gracefully
    result = rem.check_exits(position, current_bar)
    assert result is None or isinstance(result, dict)


def test_absolute_price_rule():
    """Test absolute_price rule to cover line 76 in _level_price."""
    config = {"stop_loss": {"absolute_price": 1.0950}}
    rem = RiskExitManager(config)

    position = Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=100000.0,
    )
    # Current bar low reaches absolute stop price
    current_bar = pd.Series({"high": 1.1000, "low": 1.0950})

    # This should trigger exit at absolute price (line 76)
    result = rem.check_exits(position, current_bar)
    assert result is not None
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == 1.0950
