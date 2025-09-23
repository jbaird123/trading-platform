# Validates: [EL-8.2], [EL-8.3]
from __future__ import annotations

from datetime import datetime

from trading_platform.execution import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_oanda_stub_flip_long_to_short_opens_new_position():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    adapter.connect()
    adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 1)},
    )
    assert pm.current_position and pm.current_position.side == "long"
    adapter.place_order(
        symbol="EURUSD",
        side="short",
        size=1.0,
        meta={"price": 0.99, "time": datetime(2023, 1, 1, 1)},
    )
    assert pm.current_position and pm.current_position.side == "short"
    # One trade closed during flip
    assert len(pm.trades) == 1


def test_oanda_stub_without_pm_only_logs_events():
    adapter = OandaStubAdapter(pm=None)
    adapter.connect()
    res = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 1)},
    )
    assert res.status == "accepted"
    assert adapter.events and adapter.events[-1]["symbol"] == "EURUSD"


def test_oanda_stub_same_side_noop_flat_noop_and_shutdown():
    pm = PortfolioManager(initial_cash=0.0)
    adapter = OandaStubAdapter(pm=pm)
    adapter.connect()
    # Open long, then send another long at a new price (should not close/reopen)
    adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 2)},
    )
    pos_id = (
        (pm.current_position.symbol, pm.current_position.side)
        if pm.current_position
        else None
    )
    adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.001, "time": datetime(2023, 1, 2, 1)},
    )
    pos_id2 = (
        (pm.current_position.symbol, pm.current_position.side)
        if pm.current_position
        else None
    )
    assert pos_id2 == pos_id  # unchanged

    # Close to flat
    adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.002, "time": datetime(2023, 1, 2, 2)},
    )
    assert pm.current_position is None
    # Now send flat again with no position: should be a no-op branch
    adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.003, "time": datetime(2023, 1, 2, 3)},
    )

    # Shutdown branch
    adapter.shutdown()
    assert adapter.connected is False
