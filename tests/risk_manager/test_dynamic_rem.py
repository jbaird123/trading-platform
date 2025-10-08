"""
Tests for DynamicREM (Dynamic Risk & Exit Manager).

Tasks 12-21: Epic 2, Features 2.1-2.2
Validates dynamic position management with breakeven, partial exits,
and volatility-aware trailing stops.
"""

from __future__ import annotations

from datetime import datetime

from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.dynamic_rem import DynamicREM


def test_breakeven_trigger():
    """Task 12: Test breakeven trigger when trade reaches +0.75R.

    Validates: Epic 2.1, Feature 2.1, Task 12
    When a position reaches 0.75R profit, the stop-loss should move to
    breakeven (entry price).
    """
    # Create DynamicREM with breakeven threshold
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "breakeven_threshold": 0.75,  # Move to breakeven at +0.75R
    }

    rem = DynamicREM(config)

    # Create a long position
    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,  # Risk of $150
        bars_held=5,
    )

    # Current price at +0.75R
    # If risk is $150 for 1.5 ATR, 1R = $100
    # +0.75R = $75 profit
    # entry=1.1000, need to move up $75 on 10k units = 0.0075 pips
    # Actual R calculation: risk_amount / size = distance
    # distance = 150 / 10000 = 0.015
    # 1R = 0.015, so 0.75R = 0.01125
    current_price = 1.1000 + 0.01125
    atr = 0.010  # ATR value
    initial_stop = 1.1000 - (1.5 * 0.010)  # Original stop at -1.5 ATR

    # Manage position with current price
    updated_stop, updated_tp = rem.manage_position(
        position, current_price=current_price, atr=atr, initial_stop=initial_stop
    )

    # Stop should now be at breakeven (entry price)
    assert updated_stop is not None
    assert abs(updated_stop - 1.1000) < 0.0001  # Breakeven = entry price
