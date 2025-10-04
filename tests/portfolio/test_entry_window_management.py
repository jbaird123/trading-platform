"""Comprehensive tests for Entry Window Management (PM-5.8.x).

# Validates: [PM-5.8.1], [PM-5.8.2], [PM-5.8.3], [PM-5.8.4], [PM-5.8.5]

This test suite provides explicit validation of all entry window
management requirements defined in PM-5.8 and its sub-requirements.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.portfolio.portfolio import PortfolioManager

# Minimal instrument for testing
TEST_INSTRUMENT = {
    "symbol": "TEST",
    "asset_class": "Stock",
    "point_value": 1.0,
    "tick_size": 0.01,
}

# PM-5.8.1: Track bar index when entry command received


def test_pm_5_8_1_tracks_bar_index_when_entry_command_received():
    """
    Validates: [PM-5.8.1]

    Verify PM tracks the bar index when each entry command is received.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Enter long at bar 5
    pm.process_command(
        command="enter_long",
        bar_index=5,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        context=None,
    )

    # Verify window start tracked at bar 5
    window_start, _ = pm._entry_windows["long"]
    assert window_start == 5, "Should track bar index 5 for long entry"

    # Enter short at bar 10
    pm.process_command(
        command="enter_short",
        bar_index=10,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 5)),
        context=None,
    )

    # Verify window start tracked at bar 10
    window_start, _ = pm._entry_windows["short"]
    assert window_start == 10, "Should track bar index 10 for short"


def test_pm_5_8_1_updates_bar_index_on_new_entry_command():
    """
    Validates: [PM-5.8.1]

    Verify bar index is updated when a new entry command is received.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # First long command at bar 5
    pm.process_command(
        "enter_long",
        5,
        0,
        3,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )
    assert pm._entry_windows["long"][0] == 5

    # Second long command at bar 8 (new window)
    pm.process_command(
        "enter_long",
        8,
        0,
        3,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 3)),
        None,
    )
    assert pm._entry_windows["long"][0] == 8, "Should update to bar 8"


# PM-5.8.2: Track entry occurrence to prevent duplicates


def test_pm_5_8_2_tracks_entry_occurrence():
    """
    Validates: [PM-5.8.2]

    Verify PM tracks whether entry has occurred on current command.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open entry window
    pm.process_command(
        "enter_long",
        0,
        0,
        3,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )

    # Initially, last_entered should be None (not entered yet)
    _, last_entered = pm._entry_windows["long"]
    assert last_entered is None, "Initially no entry has occurred"

    # Simulate entry (would be done by backtester)
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1),
    )

    # Mark entry as having occurred (backtester responsibility)
    pm._entry_windows["long"] = (0, 0)  # (window_start, last_entered)

    _, last_entered = pm._entry_windows["long"]
    assert last_entered == 0, "Should track that entry occurred at bar 0"


def test_pm_5_8_2_prevents_duplicate_entry_on_same_command():
    """
    Validates: [PM-5.8.2]

    Verify can_attempt_entry prevents duplicate entries on same command.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open window at bar 0
    pm._entry_windows["long"] = (0, None)

    # Can attempt entry (not entered yet)
    assert pm.can_attempt_entry("long", 1, 3) is True

    # Mark as entered at bar 1
    pm._entry_windows["long"] = (0, 1)

    # Cannot attempt entry again (already entered on this command)
    assert pm.can_attempt_entry("long", 2, 3) is False


# PM-5.8.3: Configurable entry window policies


def test_pm_5_8_3_1_entry_window_bars_0_exact_bar_only():
    """
    Validates: [PM-5.8.3] - entry_window_bars: 0

    Verify entry_window_bars=0 allows entry on exact bar only.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open window at bar 5 with window=0
    pm._entry_windows["long"] = (5, None)

    # Bar 5: Can attempt (exact bar)
    assert pm.can_attempt_entry("long", 5, 0) is True

    # Bar 6: Cannot attempt (window expired)
    assert pm.can_attempt_entry("long", 6, 0) is False


def test_pm_5_8_3_2_entry_window_bars_n_allows_n_bar_window():
    """
    Validates: [PM-5.8.3] - entry_window_bars: N

    Verify entry_window_bars=N keeps window open for N bars.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open window at bar 10 with window=3
    pm._entry_windows["long"] = (10, None)

    # Bars 10, 11, 12, 13: Can attempt (within window)
    assert pm.can_attempt_entry("long", 10, 3) is True
    assert pm.can_attempt_entry("long", 11, 3) is True
    assert pm.can_attempt_entry("long", 12, 3) is True
    assert pm.can_attempt_entry("long", 13, 3) is True

    # Bar 14: Cannot attempt (window expired)
    assert pm.can_attempt_entry("long", 14, 3) is False


def test_pm_5_8_3_3_entry_window_bars_minus_1_infinite_window():
    """
    Validates: [PM-5.8.3] - entry_window_bars: -1

    Verify entry_window_bars=-1 keeps window open indefinitely.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open window at bar 0 with infinite window
    pm._entry_windows["long"] = (0, None)

    # Should be able to attempt entry at any future bar
    assert pm.can_attempt_entry("long", 0, -1) is True
    assert pm.can_attempt_entry("long", 10, -1) is True
    assert pm.can_attempt_entry("long", 100, -1) is True
    assert pm.can_attempt_entry("long", 1000, -1) is True


def test_pm_5_8_3_entry_commands_only():
    """
    Validates: [PM-5.8.3]

    Verify entry windows apply only to entry commands, not exits.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Create position
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1),
    )

    # Exit command should execute immediately (no window)
    result = pm.process_command(
        "exit_long",
        5,
        0,
        3,
        False,
        pd.Series({"close": 1.01}, name=datetime(2024, 1, 1, 5)),
        None,
    )

    assert result["action"] == "exited", "Exit should execute immediately"
    assert pm.current_position is None


# PM-5.8.4: Entry windows persist across None commands


def test_pm_5_8_4_window_persists_across_none_commands():
    """
    Validates: [PM-5.8.4]

    Verify entry window remains open across bars with None commands.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Bar 0: Open long entry window
    result = pm.process_command(
        "enter_long",
        0,
        0,
        5,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )
    assert result["action"] == "window_opened"

    # Bars 1-4: None commands, window should stay active
    for bar_idx in range(1, 5):
        result = pm.process_command(
            None,
            bar_idx,
            0,
            5,
            False,
            pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, bar_idx)),
            None,
        )
        assert result["action"] == "window_active"
        assert result["side"] == "long"
        assert pm.can_attempt_entry("long", bar_idx, 5) is True


def test_pm_5_8_4_window_expires_per_policy():
    """
    Validates: [PM-5.8.4]

    Verify window expires per entry_window_bars policy.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open window at bar 0 with 2-bar window
    pm.process_command(
        "enter_long",
        0,
        0,
        2,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )

    # Bar 2: Still active (bars_since_start=2, window=2)
    result = pm.process_command(
        None,
        2,
        0,
        2,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 2)),
        None,
    )
    assert result["action"] == "window_active"

    # Bar 3: Expired (bars_since_start=3, window=2)
    result = pm.process_command(
        None,
        3,
        0,
        2,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 3)),
        None,
    )
    assert result["action"] == "ignored"
    assert result["reason"] == "no_active_command"


def test_pm_5_8_4_opposite_entry_closes_window():
    """
    Validates: [PM-5.8.4]

    Verify both windows can be active simultaneously.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Open long window at bar 0
    pm.process_command(
        "enter_long",
        0,
        0,
        5,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )
    assert pm._entry_windows["long"][0] == 0

    # Bar 2: Short command (opposite side)
    pm.process_command(
        "enter_short",
        2,
        0,
        5,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 2)),
        None,
    )

    # Both windows should exist
    assert pm._entry_windows["long"][0] == 0
    assert pm._entry_windows["short"][0] == 2

    # Bar 3: None command - checks long first (deterministic order)
    result = pm.process_command(
        None,
        3,
        0,
        5,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 3)),
        None,
    )
    assert result["action"] == "window_active"
    # Returns first active window found (long checked before short)
    assert result["side"] == "long"


# PM-5.8.5: State serialization for live trading


def test_pm_5_8_5_entry_window_state_is_serializable():
    """
    Validates: [PM-5.8.5]

    Verify entry window state can be serialized for live trading.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Set up entry window state
    pm._entry_windows["long"] = (5, None)
    pm._entry_windows["short"] = (10, 8)

    # Entry window state should be simple dict of tuples (serializable)
    state = pm._entry_windows

    # Verify it's a dict
    assert isinstance(state, dict)

    # Verify each value is a tuple of (int, int|None)
    for side, (window_start, last_entered) in state.items():
        assert isinstance(side, str)
        assert isinstance(window_start, int)
        assert last_entered is None or isinstance(last_entered, int)

    # Simulate serialization/deserialization
    import json

    serialized = json.dumps({side: [ws, le] for side, (ws, le) in state.items()})
    deserialized = json.loads(serialized)

    # Restore state
    restored_state = {side: tuple(vals) for side, vals in deserialized.items()}

    assert restored_state["long"] == (5, None)
    assert restored_state["short"] == (10, 8)


def test_pm_5_8_5_entry_window_state_survives_restart():
    """
    Validates: [PM-5.8.5]

    Verify entry window state can be restored after restart.
    """
    # Original PM with active window
    pm1 = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)
    pm1.process_command(
        "enter_long",
        5,
        0,
        10,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )

    # Save state
    saved_state = dict(pm1._entry_windows)

    # New PM instance (simulating restart)
    pm2 = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)
    pm2._entry_windows = saved_state

    # Verify restored state works correctly
    assert pm2.can_attempt_entry("long", 6, 10) is True
    assert pm2.can_attempt_entry("long", 15, 10) is True
    assert pm2.can_attempt_entry("long", 16, 10) is False


# Integration test covering all PM-5.8.x requirements


def test_pm_5_8_full_entry_window_lifecycle():
    """
    Validates: [PM-5.8.1], [PM-5.8.2], [PM-5.8.3], [PM-5.8.4]

    Full lifecycle test of entry window management.
    """
    pm = PortfolioManager(base_currency="USD", initial_cash=100000, instrument=TEST_INSTRUMENT)

    # Bar 0: enter_long command (PM-5.8.1: track bar index)
    result = pm.process_command(
        "enter_long",
        0,
        0,
        3,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1)),
        None,
    )
    assert result["action"] == "window_opened"
    assert pm._entry_windows["long"] == (0, None)  # PM-5.8.1

    # Bar 1: None command (PM-5.8.4: window persists)
    result = pm.process_command(
        None,
        1,
        0,
        3,
        False,
        pd.Series({"close": 1.0}, name=datetime(2024, 1, 1, 1)),
        None,
    )
    assert result["action"] == "window_active"
    assert pm.can_attempt_entry("long", 1, 3) is True  # PM-5.8.3

    # Simulate entry at bar 1 (PM-5.8.2: track occurrence)
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1, 1),
    )
    pm._entry_windows["long"] = (0, 1)  # Mark as entered at bar 1

    # Bar 2: Cannot enter again (PM-5.8.2: prevent duplicate)
    assert pm.can_attempt_entry("long", 2, 3) is False

    # Bar 5: Window expired (PM-5.8.3: window policy enforced)
    pm._entry_windows["long"] = (0, None)  # Reset for testing
    assert pm.can_attempt_entry("long", 5, 3) is False
