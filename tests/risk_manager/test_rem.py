"""Risk & Exit Manager tests.

# Validates: [REM-6.1], [REM-6.2], [REM-6.3]
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager

# Validates: [REM-6.1], [REM-6.2], [REM-6.3], [REM-6.4]


@pytest.fixture(scope="module")
def rem_config() -> dict:
    """Creates a REM config dict for testing."""
    return {
        "name": "Test REM Config",
        "stop_loss": {"type": "fixed_pips", "pips": 50.0},
        "take_profit": {"type": "offset", "price_offset": 0.0060},
    }


@pytest.fixture(scope="module")
def instrument_config() -> dict:
    """Creates an instrument config dict for testing."""
    return {"pip_location": 0.0001}


def test_rem_config_loading(rem_config: dict, instrument_config: dict):
    """Tests that the REM can be instantiated and loads a config."""
    rem = RiskExitManager(config=rem_config, instrument=instrument_config)
    assert rem.config is not None
    assert rem.config.name == "Test REM Config"
    assert rem.config.stop_loss.type == "fixed_pips"


@pytest.mark.parametrize(
    "side, entry_price, expected_sl, expected_tp",
    [
        ("long", 1.1000, 1.0950, 1.1060),
        ("short", 1.1000, 1.1050, 1.0940),
    ],
)
def test_rem_check_exits(
    rem_config: dict,
    instrument_config: dict,
    side: str,
    entry_price: float,
    expected_sl: float,
    expected_tp: float,
):
    """Test that REM calculates stop and take profit levels correctly."""
    rem = RiskExitManager(config=rem_config, instrument=instrument_config)

    # Create a position
    position = Position(
        symbol="EURUSD",
        side=side,
        entry_price=entry_price,
        entry_mid_price=entry_price,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Create bars that trigger both stop and TP (separate checks)
    # First check stop
    stop_bar = pd.Series(
        {
            "open": entry_price,
            "high": entry_price + 0.01 if side == "short" else entry_price,
            "low": entry_price - 0.01 if side == "long" else entry_price,
            "close": entry_price,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits(position, stop_bar)
    if result:
        assert result["exit_price"] == pytest.approx(expected_sl)
        assert result["reason"] == "stop-loss"

    # Check TP
    tp_bar = pd.Series(
        {
            "open": entry_price,
            "high": entry_price + 0.01 if side == "long" else entry_price,
            "low": entry_price - 0.01 if side == "short" else entry_price,
            "close": entry_price,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits(position, tp_bar)
    if result:
        assert result["exit_price"] == pytest.approx(expected_tp)
        assert result["reason"] == "take-profit"


def test_rem_pluggable_nature():
    """Test that REM can be plugged into other components."""

    class MockBacktester:
        def __init__(self, rem: RiskExitManager):
            self.rem = rem

        def run(self):
            assert self.rem is not None
            assert self.rem.config is not None
            assert self.rem.config.stop_loss.type == "fixed_pips"
            assert self.rem.config.stop_loss.pips == 100.0

    config_dict = {"stop_loss": {"type": "fixed_pips", "pips": 100.0}}
    instrument_dict = {"pip_location": 0.0001}
    rem = RiskExitManager(config=config_dict, instrument=instrument_dict)
    backtester = MockBacktester(rem=rem)
    backtester.run()


# New tests for execution model refactor (Part 3)


def test_check_exits_with_stop_triggered_returns_descriptor():
    """
    Test check_exits_intrabar returns descriptor when stop-loss triggered.

    When bar low (for long) crosses below stop-loss price, should return
    should_close descriptor with exit_price equal to stop-loss level.
    """
    config_dict = {
        "stop_loss": {"type": "offset", "price_offset": 0.0050},
        "take_profit": {"type": "offset", "price_offset": 0.0100},
    }
    instrument_dict = {"pip_location": 0.0001}
    rem = RiskExitManager(config=config_dict, instrument=instrument_dict)

    # Long position with entry at 1.1000, stop at 1.0950
    position = Position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        entry_mid_price=1.1000,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Bar where low triggers stop
    current_bar = pd.Series(
        {
            "open": 1.0980,
            "high": 1.0990,
            "low": 1.0940,  # Crosses below stop at 1.0950
            "close": 1.0960,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits_intrabar(position, current_bar)

    assert result is not None
    assert result["action"] == "should_close"
    assert result["reason"] == "stop-loss"
    assert result["exit_price"] == pytest.approx(1.0950)


def test_check_exits_with_take_profit_triggered_returns_descriptor():
    """
    Test check_exits_intrabar returns descriptor when take-profit triggered.

    When bar high (for long) crosses above TP price, should return
    should_close descriptor with exit_price equal to TP level.
    """
    config_dict = {
        "stop_loss": {"type": "fixed_pips", "pips": 500.0},
        "take_profit": {"type": "offset", "price_offset": 0.0100},
    }
    instrument_dict = {"pip_location": 0.0001}
    rem = RiskExitManager(config=config_dict, instrument=instrument_dict)

    # Short position with entry at 1.1000, TP at 1.0900
    position = Position(
        symbol="EURUSD",
        side="short",
        entry_price=1.1000,
        entry_mid_price=1.1000,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Bar where low triggers TP
    current_bar = pd.Series(
        {
            "open": 1.0920,
            "high": 1.0930,
            "low": 1.0890,  # Crosses below TP at 1.0900
            "close": 1.0910,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits_intrabar(position, current_bar)

    assert result is not None
    assert result["action"] == "should_close"
    assert result["reason"] == "take-profit"
    assert result["exit_price"] == pytest.approx(1.0900)


def test_check_exits_with_no_trigger_returns_none():
    """
    Test check_exits_intrabar returns None when neither stop nor TP triggered.

    When bar doesn't cross stop or TP levels, should return None.
    """
    config_dict = {
        "stop_loss": {"type": "offset", "price_offset": 0.0050},
        "take_profit": {"type": "offset", "price_offset": 0.0100},
    }
    instrument_dict = {"pip_location": 0.0001}
    rem = RiskExitManager(config=config_dict, instrument=instrument_dict)

    # Long position with entry at 1.1000, stop at 1.0950, TP at 1.1100
    position = Position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        entry_mid_price=1.1000,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Bar that doesn't trigger stop or TP
    current_bar = pd.Series(
        {
            "open": 1.1010,
            "high": 1.1020,
            "low": 1.0990,  # Above stop at 1.0950, below TP at 1.1100
            "close": 1.1005,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits_intrabar(position, current_bar)

    assert result is None
