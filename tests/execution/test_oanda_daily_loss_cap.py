# Validates: [EL-8.9]
from __future__ import annotations

from datetime import datetime

from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.execution import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_adapter_rejects_after_daily_loss_cap_hit():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm, daily_loss_cap=5.0)
    adapter.connect()
    # Open and close a losing trade to breach cap
    r1 = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 100.0, "time": datetime(2024, 1, 1, 9)},
    )
    assert r1.status == "accepted"
    r2 = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 94.0, "time": datetime(2024, 1, 1, 10)},
    )
    assert r2.status == "accepted"
    # Attempt another entry same day should be rejected by risk cap
    r3 = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 95.0, "time": datetime(2024, 1, 1, 11)},
    )
    assert r3.status == "rejected" and r3.message == "risk_cap"


def test_adapter_blackout_has_priority_over_risk_cap():
    policy = TradingWindowPolicy.from_config(blackout_utc=[("00:00", "23:59")])
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm, policy=policy, daily_loss_cap=5.0)
    adapter.connect()
    # Even without any trades, blackout should reject first
    res = adapter.place_order(
        symbol="EURUSD",
        side="long",
        size=1.0,
        meta={"price": 1.0, "time": datetime(2024, 1, 1, 12)},
    )
    assert res.status == "rejected" and res.message == "blackout"
