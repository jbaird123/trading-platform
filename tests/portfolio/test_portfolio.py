from __future__ import annotations

from datetime import datetime

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
        symbol="EUR_USD",
        entry_time=entry_time,
        entry_price=1.1000,
        side="long",
        size=10000,
    )

    assert portfolio._open_position is not None
    assert portfolio._open_position.entry_price == 1.1000
    assert portfolio._open_position.side == "long"
    assert portfolio._open_position.symbol == "EUR_USD"

    # Close the position with a profit
    portfolio.close_position(
        exit_price=1.1050, exit_time=exit_time, exit_reason="signal"
    )

    # Verify state after closing
    assert portfolio._open_position is None
    assert len(portfolio.trades) == 1

    # Verify the recorded trade
    trade = portfolio.trades[0]
    assert trade.entry_price == 1.1000
    assert trade.exit_price == 1.1050
    assert trade.side == "long"
    assert trade.symbol == "EUR_USD"
    assert trade.exit_reason == "signal"
    # PnL = (1.1050 - 1.1000) * 10000 = 5.0
    assert trade.pnl == pytest.approx(50.0)

    # Verify cash balance was updated
    assert portfolio.cash == pytest.approx(100000 + 50.0)


@requires("PM-5.1", "PM-5.2", "PM-5.7")
def test_open_and_close_short_position_with_loss():
    """Verify opening and closing a short position calculates PnL correctly."""
    portfolio = PortfolioManager(initial_cash=100000)
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
    portfolio.close_position(exit_price=152.5, exit_time=exit_time)

    assert portfolio._open_position is None
    assert len(portfolio.trades) == 1

    trade = portfolio.trades[0]
    # PnL = (150.0 - 152.5) * 1000 = -2500.0
    assert trade.pnl == pytest.approx(-2500.0)
    assert portfolio.cash == pytest.approx(100000 - 2500.0)


@requires("PM-5.1")
def test_cannot_open_position_if_one_is_already_open():
    """Verify that a new position cannot be opened if one is active."""
    portfolio = PortfolioManager()
    portfolio.create_new_position(
        symbol="EUR_USD",
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
    assert portfolio._open_position.symbol == "EUR_USD"


@requires("PM-5.1", "PM-5.2")
def test_close_position_does_nothing_if_no_position_is_open():
    """Verify that closing a position does nothing when the portfolio is flat."""
    portfolio = PortfolioManager(initial_cash=100000)
    assert portfolio._open_position is None

    # Attempt to close a non-existent position
    portfolio.close_position(exit_price=1.0, exit_time=datetime.now())

    # Verify that no trades were created and cash is unchanged
    assert len(portfolio.trades) == 0
    assert portfolio.cash == 100000
