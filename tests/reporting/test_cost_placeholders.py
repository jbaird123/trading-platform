# Validates: [JSON-11.12]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _make_trade(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.001,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_trades_include_cost_breakdown_placeholders():
    brief = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[_make_trade(datetime(2023, 1, 1), 10.0)],
        initial_cash=1000.0,
        fill_policy={"policy": "market"},
        tie_break_policy={"rule": "stop_then_tp"},
    )
    assert isinstance(brief["trades"], list) and len(brief["trades"]) == 1
    cb = brief["trades"][0].get("cost_breakdown")
    assert cb is not None
    assert cb.get("spread") == 0.0
    assert cb.get("commission") == 0.0
    assert cb.get("slippage") == 0.0
