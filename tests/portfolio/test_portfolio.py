# Validates: [PM-5.1], [PM-5.3], [PM-5.4], [PM-5.5], [PM-5.6]
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
    portfolio.close_position(
        exit_price=152.5, exit_time=exit_time, context_at_exit=None
    )

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


@requires("PM-5.8", "PM-5.8.1", "PM-5.8.2", "PM-5.8.3")
def test_entry_window_event_based():
    """Test event-based entry (window=0): only enter on exact signal transition."""
    portfolio = PortfolioManager(initial_cash=100000)

    # Bar 0: Signal transitions to "long" (warmup=0)
    portfolio.update_signal_state("long", bar_index=0, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 0, entry_window_bars=0)

    # Bar 1: Signal still "long", no transition
    portfolio.update_signal_state("long", bar_index=1, warmup_threshold=0)
    assert not portfolio.should_attempt_entry("long", 1, entry_window_bars=0)


@requires("PM-5.8", "PM-5.8.1", "PM-5.8.2", "PM-5.8.3")
def test_entry_window_delayed_entry():
    """Test delayed entry (window=3): can enter within 3 bars of transition."""
    portfolio = PortfolioManager(initial_cash=100000)

    # Bar 0: Signal transitions to "long"
    portfolio.update_signal_state("long", bar_index=0, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 0, entry_window_bars=3)

    # Bar 1: Still within window
    portfolio.update_signal_state("long", bar_index=1, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 1, entry_window_bars=3)

    # Bar 2: Still within window
    portfolio.update_signal_state("long", bar_index=2, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 2, entry_window_bars=3)

    # Bar 3: Still within window (exactly at edge: 3 - 0 = 3, and 3 <= 3)
    portfolio.update_signal_state("long", bar_index=3, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 3, entry_window_bars=3)

    # Bar 4: Window expired (4 - 0 = 4, and 4 > 3)
    portfolio.update_signal_state("long", bar_index=4, warmup_threshold=0)
    assert not portfolio.should_attempt_entry("long", 4, entry_window_bars=3)


@requires("PM-5.8", "PM-5.8.1", "PM-5.8.2", "PM-5.8.3")
def test_entry_window_infinite():
    """Test infinite window (window=-1): always try when signal active."""
    portfolio = PortfolioManager(initial_cash=100000)

    # Bar 0: Signal transitions to "long"
    portfolio.update_signal_state("long", bar_index=0, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 0, entry_window_bars=-1)

    # Bar 100: Still should attempt (infinite window)
    portfolio.update_signal_state("long", bar_index=100, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 100, entry_window_bars=-1)


@requires("PM-5.8", "PM-5.8.2", "PM-5.8.4")
def test_entry_window_prevents_reentry_after_entry():
    """Test that marking entry prevents re-entry on same signal instance."""
    portfolio = PortfolioManager(initial_cash=100000)

    # Bar 0: Signal transitions to "long"
    portfolio.update_signal_state("long", bar_index=0, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 0, entry_window_bars=5)

    # Mark entry at bar 0
    portfolio.mark_entry_on_signal("long", 0)

    # Bar 1: Signal still "long", but already entered
    portfolio.update_signal_state("long", bar_index=1, warmup_threshold=0)
    assert not portfolio.should_attempt_entry("long", 1, entry_window_bars=5)

    # Bar 2: Still can't enter (already entered on this signal)
    portfolio.update_signal_state("long", bar_index=2, warmup_threshold=0)
    assert not portfolio.should_attempt_entry("long", 2, entry_window_bars=5)


@requires("PM-5.8", "PM-5.8.4")
def test_entry_window_resets_on_new_transition():
    """Test that new signal transition resets the entry window."""
    portfolio = PortfolioManager(initial_cash=100000)

    # Bar 0: Signal transitions to "long"
    portfolio.update_signal_state("long", bar_index=0, warmup_threshold=0)
    portfolio.mark_entry_on_signal("long", 0)

    # Bar 5: Signal transitions to "short" (new transition)
    portfolio.update_signal_state("short", bar_index=5, warmup_threshold=0)
    assert portfolio.should_attempt_entry("short", 5, entry_window_bars=3)

    # Bar 10: Signal transitions back to "long" (resets long window)
    portfolio.update_signal_state("long", bar_index=10, warmup_threshold=0)
    assert portfolio.should_attempt_entry("long", 10, entry_window_bars=3)


@requires("PM-5.8", "PM-5.8.1")
def test_entry_window_warmup_threshold():
    """Test that warmup threshold triggers a transition even if signal unchanged."""
    portfolio = PortfolioManager(initial_cash=100000)

    # Bar 0: Signal is "long", transition detected (flat -> long)
    portfolio.update_signal_state("long", bar_index=0, warmup_threshold=50)
    # But bar 0 < warmup threshold (50), so should_attempt_entry with warmup check would fail
    # However, our should_attempt_entry doesn't check warmup - that's done in backtester
    # So this test needs to verify the warmup threshold transition behavior

    # Simulate: signal already "short" during warmup period
    portfolio._prev_signal = "short"  # Manually set to test warmup transition
    portfolio._entry_windows["short"] = (0, None)

    # Bars 0-49: Signal is "short", no transition
    for i in range(1, 50):
        signal_changed = portfolio.update_signal_state(
            "short", bar_index=i, warmup_threshold=50
        )
        assert not signal_changed  # No transition during warmup

    # Bar 50: At warmup threshold, signal="short" triggers transition
    signal_changed = portfolio.update_signal_state(
        "short", bar_index=50, warmup_threshold=50
    )
    assert signal_changed  # Warmup threshold should trigger transition
    assert portfolio.should_attempt_entry("short", 50, entry_window_bars=3)
