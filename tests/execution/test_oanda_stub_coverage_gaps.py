# Coverage gaps for execution/oanda_stub.py
# Missing branch: 103->119 (side == "flat" and self.pm.current_position)
from __future__ import annotations

from datetime import datetime

from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_oanda_stub_place_order_flat_with_position():
    """side='flat' should close an existing position (branch 103->119)."""
    # Create portfolio manager with an existing position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 10))

    # Verify position exists
    assert pm.current_position is not None
    assert pm.current_position.side == "long"

    # Create OandaStubAdapter
    adapter = OandaStubAdapter(pm)

    # Place order with side="flat" - should trigger branch 103->119
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Order should be accepted
    assert result.status == "accepted"

    # Position should be closed (branch 103->119 closes position)
    assert pm.current_position is None

    # Should have one trade recorded
    assert len(pm.trades) == 1
    assert pm.trades[0].exit_reason == "flat"
    assert pm.trades[0].exit_price == 1.1100


def test_oanda_stub_place_order_flat_without_position():
    """Test place_order with side='flat' when no current position exists."""
    # Create portfolio manager without position
    pm = PortfolioManager(initial_cash=1000.0)

    # Verify no position exists
    assert pm.current_position is None

    # Create OandaStubAdapter
    adapter = OandaStubAdapter(pm)

    # Place order with side="flat" - should not trigger branch 103->119
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Order should be accepted but no position changes
    assert result.status == "accepted"
    assert pm.current_position is None
    assert len(pm.trades) == 0
