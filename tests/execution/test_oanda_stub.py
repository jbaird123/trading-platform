from __future__ import annotations

from datetime import datetime

from trading_platform.execution import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_oanda_stub_logs_and_updates_pm():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    adapter.connect()

    # Open long
    res1 = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 1)},
    )
    assert res1.status == "accepted"
    assert adapter.events and adapter.events[-1]["order_id"] == res1.order_id
    assert pm.current_position is not None and pm.current_position.side == "long"

    # Flatten
    res2 = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.001, "time": datetime(2023, 1, 1, 1)},
    )
    assert res2.status == "accepted"
    assert pm.current_position is None
    assert len(pm.trades) == 1
