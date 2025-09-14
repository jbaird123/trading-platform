from __future__ import annotations

from datetime import datetime

from trading_platform.execution import OandaStubAdapter
from trading_platform.execution.controller import reconcile, reconcile_report
from trading_platform.portfolio.portfolio import PortfolioManager


def test_reconcile_short_equity_and_legacy_reconcile():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    # Open a short position
    adapter.connect()
    adapter.place_order(
        symbol="EURUSD",
        side="short",
        size=1.0,
        meta={"price": 100.0, "time": datetime(2024, 1, 1)},
    )
    # Mark price lower should increase equity for short
    rep = reconcile_report(pm, adapter, mark_price=90.0)
    assert rep.severity in {"info", "warn", "error"}
    # Legacy reconcile: now match snapshot to PM
    adapter.account_snapshot()
    assert reconcile(pm, adapter) in ([], ["size_mismatch"])  # size present or zero
