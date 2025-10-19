"""
Tests for 1-minute trailing stop processor.

These tests verify that the 1-minute bar processor correctly:
- Tracks trailing stop movement across bars
- Detects stop and take-profit hits
- Applies tie-breaker policy when both hit on same bar
- Returns exit at the stop/TP level (not next bar open)
"""

import pandas as pd


def test_trailing_stop_hit_on_specific_minute():
    """Test that stop is hit on correct minute bar and returns stop level."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Create 60 1-minute bars for an hour
    # Long position at 1.0600, trailing stop 20 pips (0.0020)
    # Bar 15: Price drops to hit stop at 1.0580
    bars = []
    for i in range(60):
        if i < 15:
            # Price stays at or below entry (no favorable movement)
            bars.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0595, "close": 1.0600}
            )
        elif i == 15:
            # Price drops, hitting stop at entry - 20 pips
            bars.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0575, "close": 1.0580}
            )
        else:
            # After stop hit
            bars.append(
                {"open": 1.0580, "high": 1.0585, "low": 1.0575, "close": 1.0580}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,  # 20 pips
        take_profit_price=None,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 15
    assert result["exit_price"] == 1.0580  # Entry - 20 pips
    assert result["exit_reason"] == "stop-loss"


def test_take_profit_hit_no_trailing_stop():
    """Test that TP is hit and returned when no stop hit."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Long position at 1.0600, TP at 1.0650
    # Bar 20: Price rallies to TP
    bars = []
    for i in range(60):
        if i < 20:
            # Price rallying
            bars.append(
                {
                    "open": 1.0600 + i * 0.0002,
                    "high": 1.0610 + i * 0.0002,
                    "low": 1.0600 + i * 0.0002,
                    "close": 1.0605 + i * 0.0002,
                }
            )
        elif i == 20:
            # TP hit
            bars.append(
                {"open": 1.0640, "high": 1.0655, "low": 1.0640, "close": 1.0650}
            )
        else:
            bars.append(
                {"open": 1.0650, "high": 1.0655, "low": 1.0645, "close": 1.0650}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,
        take_profit_price=1.0650,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 20
    assert result["exit_price"] == 1.0650
    assert result["exit_reason"] == "take-profit"


def test_stop_hit_before_take_profit():
    """Test that stop hit first when both eventually hit."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Stop hit on bar 10, TP would hit on bar 20
    bars = []
    for i in range(60):
        if i < 10:
            # No favorable movement - keep high at entry
            bars.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0595, "close": 1.0600}
            )
        elif i == 10:
            # Stop hit
            bars.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0575, "close": 1.0580}
            )
        else:
            bars.append(
                {"open": 1.0580, "high": 1.0585, "low": 1.0575, "close": 1.0580}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,
        take_profit_price=1.0650,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 10
    assert result["exit_price"] == 1.0580
    assert result["exit_reason"] == "stop-loss"


def test_both_hit_same_bar_stop_then_tp_policy():
    """Test tie-breaker: stop_then_tp policy when both hit on same bar."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Bar 10: Both stop and TP in range
    bars = []
    for i in range(60):
        if i < 10:
            # No favorable movement
            bars.append(
                {"open": 1.0600, "high": 1.0600, "low": 1.0595, "close": 1.0600}
            )
        elif i == 10:
            # Wide bar - both stop and TP hit
            bars.append(
                {"open": 1.0600, "high": 1.0650, "low": 1.0575, "close": 1.0620}
            )
        else:
            bars.append(
                {"open": 1.0620, "high": 1.0625, "low": 1.0615, "close": 1.0620}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,
        take_profit_price=1.0650,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 10
    assert result["exit_price"] == 1.0580  # Stop price
    assert result["exit_reason"] == "stop-loss"


def test_both_hit_same_bar_tp_then_stop_policy():
    """Test tie-breaker: tp_then_stop policy when both hit on same bar."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Same scenario as above but different policy
    bars = []
    for i in range(60):
        if i < 10:
            bars.append(
                {"open": 1.0600, "high": 1.0610, "low": 1.0595, "close": 1.0600}
            )
        elif i == 10:
            # Wide bar - both stop and TP hit
            bars.append(
                {"open": 1.0600, "high": 1.0650, "low": 1.0575, "close": 1.0620}
            )
        else:
            bars.append(
                {"open": 1.0620, "high": 1.0625, "low": 1.0615, "close": 1.0620}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,
        take_profit_price=1.0650,
        tie_break_policy="tp_then_stop",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 10
    assert result["exit_price"] == 1.0650  # TP price
    assert result["exit_reason"] == "take-profit"


def test_no_exit_in_any_bar():
    """Test that no exit when neither stop nor TP hit."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Price stays in narrow range, no exits hit
    bars = []
    for i in range(60):
        bars.append({"open": 1.0600, "high": 1.0605, "low": 1.0595, "close": 1.0600})

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,
        take_profit_price=1.0700,  # Far away
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is False
    assert result["exit_bar_index"] is None
    assert result["exit_price"] is None
    assert result["exit_reason"] is None


def test_trailing_stop_moves_up_with_favorable_movement():
    """Test that trailing stop correctly trails upward for long position."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Price rallies 40 pips, then retraces to hit trailed stop
    bars = []
    for i in range(60):
        if i < 10:
            # Price gradually rallies, but stay below 1.0640
            bars.append(
                {"open": 1.0610, "high": 1.0615, "low": 1.0605, "close": 1.0610}
            )
        elif i == 10:
            # Peak at exactly 1.0640 (40 pips up), stop should trail to 1.0620
            bars.append(
                {"open": 1.0635, "high": 1.0640, "low": 1.0630, "close": 1.0635}
            )
        elif i < 15:
            # Price stabilizes below peak
            bars.append(
                {"open": 1.0635, "high": 1.0638, "low": 1.0630, "close": 1.0635}
            )
        elif i == 15:
            # Retrace hits trailed stop at 1.0620
            bars.append(
                {"open": 1.0635, "high": 1.0635, "low": 1.0615, "close": 1.0618}
            )
        else:
            bars.append(
                {"open": 1.0635, "high": 1.0638, "low": 1.0630, "close": 1.0635}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="long",
        trailing_stop_offset=0.0020,
        take_profit_price=None,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 15
    # Stop should be at peak (1.0640) - 20 pips = 1.0620
    assert result["exit_price"] == 1.0620
    assert result["exit_reason"] == "stop-loss"


def test_short_position_trailing_stop():
    """Test trailing stop for short position (stop trails down)."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Short at 1.0600, stop starts at 1.0620
    # Price drops to 1.0560 (40 pips favorable), stop trails to 1.0580
    # Then price rallies back to hit stop
    bars = []
    for i in range(60):
        if i < 10:
            # Price gradually drops, but stay above 1.0560
            bars.append(
                {"open": 1.0590, "high": 1.0595, "low": 1.0585, "close": 1.0590}
            )
        elif i == 10:
            # Trough at exactly 1.0560, stop trails to 1.0580
            bars.append(
                {"open": 1.0565, "high": 1.0570, "low": 1.0560, "close": 1.0565}
            )
        elif i < 15:
            # Price stabilizes above trough
            bars.append(
                {"open": 1.0565, "high": 1.0570, "low": 1.0565, "close": 1.0565}
            )
        elif i == 15:
            # Rally hits trailed stop at 1.0580
            bars.append(
                {"open": 1.0565, "high": 1.0585, "low": 1.0565, "close": 1.0582}
            )
        else:
            bars.append(
                {"open": 1.0565, "high": 1.0570, "low": 1.0565, "close": 1.0565}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="short",
        trailing_stop_offset=0.0020,
        take_profit_price=None,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 15
    # Stop at trough (1.0560) + 20 pips = 1.0580
    assert result["exit_price"] == 1.0580
    assert result["exit_reason"] == "stop-loss"


def test_short_position_take_profit():
    """Test take-profit for short position."""
    from trading_platform.risk_manager.trailing_stop_utils import (
        process_1min_bars_for_trailing_stop,
    )

    # Short at 1.0600, TP at 1.0550
    bars = []
    for i in range(60):
        if i < 20:
            # Price gradually drops
            bars.append(
                {
                    "open": 1.0600 - i * 0.0002,
                    "high": 1.0605 - i * 0.0002,
                    "low": 1.0595 - i * 0.0002,
                    "close": 1.0600 - i * 0.0002,
                }
            )
        elif i == 20:
            # TP hit
            bars.append(
                {"open": 1.0560, "high": 1.0560, "low": 1.0545, "close": 1.0550}
            )
        else:
            bars.append(
                {"open": 1.0550, "high": 1.0555, "low": 1.0545, "close": 1.0550}
            )

    bars_df = pd.DataFrame(bars)

    result = process_1min_bars_for_trailing_stop(
        bars_1min=bars_df,
        entry_price=1.0600,
        side="short",
        trailing_stop_offset=0.0020,
        take_profit_price=1.0550,
        tie_break_policy="stop_then_tp",
        current_peak_or_trough=1.0600,  # Starting from entry price
    )

    assert result["exit_occurred"] is True
    assert result["exit_bar_index"] == 20
    assert result["exit_price"] == 1.0550
    assert result["exit_reason"] == "take-profit"
