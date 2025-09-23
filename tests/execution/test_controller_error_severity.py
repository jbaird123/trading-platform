# Validates: [EL-8.8]
from __future__ import annotations

from trading_platform.execution import OandaStubAdapter
from trading_platform.execution.controller import reconcile_report
from trading_platform.portfolio.portfolio import PortfolioManager


def test_reconcile_error_on_position_mismatch():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    # Force mismatch: adapter says long, size nonzero; PM flat
    adapter.account_snapshot = lambda: {
        "open_side": "long",
        "size": 1.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }
    rep = reconcile_report(pm, adapter)
    assert rep.severity == "error" and rep.position_diffs
