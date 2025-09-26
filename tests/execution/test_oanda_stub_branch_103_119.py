"""Test for the missing branch coverage 103->119 in oanda_stub.py."""

from __future__ import annotations

from datetime import datetime

from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_same_side_order_with_existing_position():
    """Test placing same-side order when position already exists.

    This should cover the missing branch 103->119 where:
    - side in {"long", "short"} is True (line 95)
    - self.pm.current_position exists but side == current_position.side
    - if not self.pm.current_position: is False (line 103)

    The branch 103->119 is the path where we DON'T create a new position
    because one already exists with the same side.
    """
    # Create portfolio manager
    pm = PortfolioManager(initial_cash=1000.0)

    # Create adapter with higher limits to allow multiple same-side positions
    adapter = OandaStubAdapter(
        pm=pm, pm_limits={"max_open_long": 2, "max_open_short": 2}
    )

    # First, create a long position
    result1 = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.1000, "time": datetime(2024, 1, 1, 10)},
    )
    assert result1.status == "accepted"
    assert pm.current_position is not None
    assert pm.current_position.side == "long"

    # Store the original position ID for comparison
    original_position_id = id(pm.current_position)

    # Now place another long order (same side) - this should NOT create a new position
    # This is the case that should hit the missing branch 103->119
    result2 = adapter.place_order(
        symbol="EURUSD",
        side="long",  # Same side as existing position
        size=2.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Order should be accepted
    assert result2.status == "accepted"

    # Position should still exist and be the same instance (not recreated)
    assert pm.current_position is not None
    assert pm.current_position.side == "long"
    assert id(pm.current_position) == original_position_id  # Same position object

    # Should have no closed trades yet (no flip occurred)
    assert len(pm.trades) == 0
