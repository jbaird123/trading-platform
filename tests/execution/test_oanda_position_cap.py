# Validates: [EL-8.9]
from __future__ import annotations

from datetime import datetime

from trading_platform.execution import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
    )


def test_oanda_stub_rejects_same_direction_over_cap():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(
        pm=pm, pm_limits={"max_open_long": 1, "max_open_short": 1}
    )
    adapter.connect()
    # Open long
    r1 = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 1)},
    )
    assert r1.status == "accepted" and pm.current_position is not None
    # Try to open another long while already long; should be rejected
    r2 = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.001, "time": datetime(2023, 1, 1, 1)},
    )
    assert r2.status == "rejected" and r2.message == "position_cap"
    # Position unchanged
    assert pm.current_position and pm.current_position.side == "long"
