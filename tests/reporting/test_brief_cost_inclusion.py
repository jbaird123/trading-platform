from __future__ import annotations

from datetime import datetime

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def test_brief_uses_trade_cost_breakdown_when_present():
    t = Trade(
        symbol="X",
        entry_time=datetime(2023, 1, 1, 0, 0),
        exit_time=datetime(2023, 1, 1, 1, 0),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
        cost_currency=0.06,
        cost_breakdown={"spread": 0.02, "commission": 0.04, "slippage": 0.0},
    )
    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[t],
        initial_cash=1000.0,
    )
    cost_bd = brief["trades"][0]["cost_breakdown"]
    assert cost_bd == {"spread": 0.02, "commission": 0.04, "slippage": 0.0}
