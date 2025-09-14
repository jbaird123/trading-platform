from __future__ import annotations

from datetime import datetime

from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.execution import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_adapter_rejects_inside_blackout_window():
    policy = TradingWindowPolicy.from_config(blackout_utc=[("00:00", "23:00")])
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm, policy=policy)
    adapter.connect()
    res = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 1, 12)},
    )
    assert res.status == "rejected"


def test_adapter_accepts_outside_blackout_window():
    policy = TradingWindowPolicy.from_config(blackout_utc=[("00:00", "23:00")])
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm, policy=policy)
    adapter.connect()
    res = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2023, 1, 1, 23, 30)},
    )
    assert res.status == "accepted"
