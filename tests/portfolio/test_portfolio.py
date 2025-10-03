# Validates: [PM-5.1], [PM-5.3], [PM-5.4], [PM-5.5], [PM-5.6]
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.utils.testing import requires


@requires("PM-5.1", "PM-5.2")
def test_portfolio_initialization():
    """Verify the portfolio initializes with correct default values."""
    portfolio = PortfolioManager(initial_cash=50000)
    assert portfolio.initial_cash == 50000
    assert portfolio.cash == 50000
    assert portfolio._open_position is None
    assert portfolio.trades == []


@requires("PM-5.1", "PM-5.2", "PM-5.7")
def test_open_and_close_long_position():
    """Verify opening and closing a long position creates a correct trade record."""
    portfolio = PortfolioManager(initial_cash=100000)
    entry_time = datetime(2023, 1, 1, 10, 0)
    exit_time = datetime(2023, 1, 1, 11, 0)

    # Open a long position
    portfolio.create_new_position(
        symbol="EURUSD",
        entry_time=entry_time,
        entry_price=1.1000,
        side="long",
        size=10000,
    )

    assert portfolio._open_position is not None
    assert portfolio._open_position.entry_price == 1.1000
    assert portfolio._open_position.side == "long"
    assert portfolio._open_position.symbol == "EURUSD"

    # Close the position with a profit
    portfolio.close_position(
        exit_price=1.1050,
        exit_time=exit_time,
        exit_reason="signal",
        context_at_exit=None,
    )

    # Verify state after closing
    assert portfolio._open_position is None
    assert len(portfolio.trades) == 1

    # Verify the recorded trade
    trade = portfolio.trades[0]
    assert trade.entry_price == 1.1000
    assert trade.exit_price == 1.1050
    assert trade.side == "long"
    assert trade.symbol == "EURUSD"
    assert trade.exit_reason == "signal"
    # PnL = (1.1050 - 1.1000) * 10000 = 5.0
    assert trade.pnl == pytest.approx(50.0)

    # Verify cash balance was updated
    assert portfolio.cash == pytest.approx(100000 + 50.0)


@requires("PM-5.1", "PM-5.2", "PM-5.7")
def test_open_and_close_short_position_with_loss():
    """Verify opening and closing a short position calculates PnL correctly."""
    # Provide instrument definition for USD/JPY
    usdjpy_instrument = {
        "symbol": "USDJPY",
        "asset_class": "Forex",
        "point_value": 1.0,
        "tick_size": 0.001,
    }

    portfolio = PortfolioManager(initial_cash=100000, instrument=usdjpy_instrument)
    entry_time = datetime(2023, 1, 1, 12, 0)
    exit_time = datetime(2023, 1, 1, 13, 0)

    # Open a short position
    portfolio.create_new_position(
        symbol="USD_JPY",
        entry_time=entry_time,
        entry_price=150.0,
        side="short",
        size=1000,
    )

    assert portfolio._open_position is not None
    assert portfolio._open_position.side == "short"

    # Close the position with a loss (price went up)
    portfolio.close_position(
        exit_price=152.5, exit_time=exit_time, context_at_exit=None
    )

    assert portfolio._open_position is None
    assert len(portfolio.trades) == 1

    trade = portfolio.trades[0]
    # USD/JPY PnL: (150.0 - 152.5) * 1000 / avg_price
    # avg_price = (150.0 + 152.5) / 2 = 151.25
    # PnL = -2.5 * 1000 / 151.25 = -16.53 USD
    assert trade.pnl == pytest.approx(-16.53, abs=0.01)
    assert portfolio.cash == pytest.approx(100000 - 16.53, abs=0.01)


@requires("PM-5.1")
def test_cannot_open_position_if_one_is_already_open():
    """Verify that a new position cannot be opened if one is active."""
    portfolio = PortfolioManager()
    portfolio.create_new_position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.1000,
        side="long",
        size=10000,
    )

    # Store the initial open position to compare against
    initial_position = portfolio._open_position
    assert initial_position is not None

    # Attempt to open another position
    portfolio.create_new_position(
        symbol="USD_JPY",
        entry_time=datetime.now(),
        entry_price=150.0,
        side="short",
        size=5000,
    )

    # Verify that the original position is unchanged
    assert portfolio._open_position is initial_position
    assert portfolio._open_position.symbol == "EURUSD"


@requires("PM-5.1", "PM-5.2")
def test_close_position_does_nothing_if_no_position_is_open():
    """Verify that closing a position does nothing when the portfolio is flat."""
    portfolio = PortfolioManager(initial_cash=100000)
    assert portfolio._open_position is None

    # Attempt to close a non-existent position
    portfolio.close_position(
        exit_price=1.0, exit_time=datetime.now(), context_at_exit=None
    )

    # Verify that no trades were created and cash is unchanged
    assert len(portfolio.trades) == 0
    assert portfolio.cash == 100000


# Entry Window Management Tests (validates [PM-5.8])


@requires("PM-5.8")
def test_process_enter_long_command():
    """Test processing enter_long command opens entry window."""
    pm = PortfolioManager(initial_cash=100000)

    result = pm.process_command(
        command="enter_long",
        bar_index=0,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0, "open": 1.0, "high": 1.0, "low": 1.0}),
        context=None,
    )

    assert result["action"] == "window_opened"
    assert result["side"] == "long"
    assert pm.can_attempt_entry("long", 0, 3)


@requires("PM-5.8")
def test_process_exit_when_no_position():
    """Test exit command is ignored when no position exists."""
    pm = PortfolioManager(initial_cash=100000)

    result = pm.process_command(
        command="exit_long",
        bar_index=0,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0, "open": 1.0, "high": 1.0, "low": 1.0}),
        context=None,
    )

    assert result["action"] == "ignored"
    assert result["reason"] == "no_matching_position"


@requires("PM-5.8")
def test_process_enter_when_already_in_position():
    """Test enter command is ignored when already in same position."""
    pm = PortfolioManager(initial_cash=100000)

    # Enter long
    pm.process_command(
        "enter_long",
        bar_index=0,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        context=None,
    )
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1),
    )

    # Try to enter long again
    result = pm.process_command(
        "enter_long",
        bar_index=1,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 1)),
        context=None,
    )

    assert result["action"] == "ignored"
    assert result["reason"] == "already_in_position"


@requires("PM-5.8")
def test_process_flip_position():
    """Test entering opposite position with allow_flip=True."""
    pm = PortfolioManager(initial_cash=100000)

    # Enter long
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1),
    )

    # Enter short with flip allowed
    result = pm.process_command(
        "enter_short",
        bar_index=1,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=True,
        current_bar=pd.Series({"close": 1.01}, name=datetime(2024, 1, 1, 1)),
        context=None,
    )

    assert result["action"] == "window_opened"
    assert result["side"] == "short"
    assert pm.current_position is None  # Closed long
    assert len(pm.trades) == 1  # Long trade closed


@requires("PM-5.8")
def test_entry_window_remains_open_with_none_commands():
    """Test entry window stays open across bars with None commands."""
    pm = PortfolioManager(initial_cash=100000)

    # Bar 0: enter_long command
    result = pm.process_command(
        "enter_long",
        bar_index=0,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        context=None,
    )
    assert result["action"] == "window_opened"

    # Bar 1: None command (window should stay active)
    result = pm.process_command(
        None,
        bar_index=1,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 1)),
        context=None,
    )
    assert result["action"] == "window_active"
    assert result["side"] == "long"
    assert pm.can_attempt_entry("long", 1, 3)

    # Bar 4: Window expired
    result = pm.process_command(
        None,
        bar_index=4,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 4)),
        context=None,
    )
    assert result["action"] == "ignored"
    assert not pm.can_attempt_entry("long", 4, 3)
