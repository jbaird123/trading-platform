"""
Tests for trailing stop ambiguity detection.

These tests verify the logic for detecting when OHLC bars are ambiguous
and require 1-minute resolution to determine the correct exit.
"""

import pandas as pd


def test_is_trailing_stop_ambiguous_when_stop_between_high_low():
    """Test that trailing stop in bar's range returns True (ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_trailing_stop_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    trailing_stop_level = 1.0625  # Between low and high

    assert is_trailing_stop_ambiguous(bar, trailing_stop_level)


def test_is_trailing_stop_not_ambiguous_when_stop_below_low():
    """Test trailing stop below bar low returns False (not ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_trailing_stop_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    trailing_stop_level = 1.0550  # Below low

    assert not is_trailing_stop_ambiguous(bar, trailing_stop_level)


def test_is_trailing_stop_not_ambiguous_when_stop_above_high():
    """Test trailing stop above bar high returns False (not ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_trailing_stop_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    trailing_stop_level = 1.0700  # Above high

    assert not is_trailing_stop_ambiguous(bar, trailing_stop_level)


def test_is_trailing_stop_ambiguous_when_stop_exactly_at_low():
    """Test trailing stop at bar low returns True (inclusive, ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_trailing_stop_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    trailing_stop_level = 1.0600  # Exactly at low

    assert is_trailing_stop_ambiguous(bar, trailing_stop_level)


def test_is_trailing_stop_ambiguous_when_stop_exactly_at_high():
    """Test trailing stop at bar high returns True (inclusive, ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_trailing_stop_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    trailing_stop_level = 1.0650  # Exactly at high

    assert is_trailing_stop_ambiguous(bar, trailing_stop_level)


def test_is_trailing_stop_ambiguous_does_not_consider_take_profit():
    """Test that function only checks stop level, not take-profit."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_trailing_stop_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    trailing_stop_level = 1.0625  # Between low and high

    # Function should return True regardless of where TP is
    # (it doesn't take TP as parameter)
    assert is_trailing_stop_ambiguous(bar, trailing_stop_level)


def test_is_fixed_stops_ambiguous_when_both_in_range():
    """Test that both fixed stop and TP in range returns True (ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_fixed_stops_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0610
    tp_level = 1.0640

    assert is_fixed_stops_ambiguous(bar, stop_level, tp_level)


def test_is_fixed_stops_not_ambiguous_when_only_stop_in_range():
    """Test that only stop in range returns False (not ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_fixed_stops_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0610  # In range
    tp_level = 1.0700  # Above high

    assert not is_fixed_stops_ambiguous(bar, stop_level, tp_level)


def test_is_fixed_stops_not_ambiguous_when_only_tp_in_range():
    """Test that only TP in range returns False (not ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_fixed_stops_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0550  # Below low
    tp_level = 1.0640  # In range

    assert not is_fixed_stops_ambiguous(bar, stop_level, tp_level)


def test_is_fixed_stops_not_ambiguous_when_neither_in_range():
    """Test that neither stop nor TP in range returns False (not ambiguous)."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_fixed_stops_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0550  # Below low
    tp_level = 1.0700  # Above high

    assert not is_fixed_stops_ambiguous(bar, stop_level, tp_level)


def test_is_fixed_stops_ambiguous_when_stop_at_low_tp_at_high():
    """Test edge case with stop exactly at low and TP exactly at high."""
    from src.trading_platform.risk_manager.exit_utils import (
        is_fixed_stops_ambiguous,
    )

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0600  # Exactly at low
    tp_level = 1.0650  # Exactly at high

    assert is_fixed_stops_ambiguous(bar, stop_level, tp_level)


def test_both_exits_in_same_bar_when_both_in_range():
    """Test that both stop and TP in range returns True."""
    from src.trading_platform.risk_manager.exit_utils import both_exits_in_same_bar

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0610
    tp_level = 1.0640

    assert both_exits_in_same_bar(bar, stop_level, tp_level)


def test_both_exits_in_same_bar_when_only_stop_in_range():
    """Test that only stop in range returns False."""
    from src.trading_platform.risk_manager.exit_utils import both_exits_in_same_bar

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0610  # In range
    tp_level = 1.0700  # Above high

    assert not both_exits_in_same_bar(bar, stop_level, tp_level)


def test_both_exits_in_same_bar_when_only_tp_in_range():
    """Test that only TP in range returns False."""
    from src.trading_platform.risk_manager.exit_utils import both_exits_in_same_bar

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0550  # Below low
    tp_level = 1.0640  # In range

    assert not both_exits_in_same_bar(bar, stop_level, tp_level)


def test_both_exits_in_same_bar_when_neither_in_range():
    """Test that neither stop nor TP in range returns False."""
    from src.trading_platform.risk_manager.exit_utils import both_exits_in_same_bar

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0550  # Below low
    tp_level = 1.0700  # Above high

    assert not both_exits_in_same_bar(bar, stop_level, tp_level)


def test_both_exits_in_same_bar_when_stop_at_low_tp_at_high():
    """Test edge case with stop exactly at low and TP exactly at high."""
    from src.trading_platform.risk_manager.exit_utils import both_exits_in_same_bar

    bar = pd.Series({"low": 1.0600, "high": 1.0650})
    stop_level = 1.0600  # Exactly at low
    tp_level = 1.0650  # Exactly at high

    assert both_exits_in_same_bar(bar, stop_level, tp_level)
