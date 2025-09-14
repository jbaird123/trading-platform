from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def test_field_definitions_included_with_key_entries():
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long",
        size=1.0,
        pnl=0.0,
    )
    b = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
    )
    fd = b.get("field_definitions", {})
    assert "overall_performance.total_pnl" in fd
    assert "equity_stats.max_drawdown" in fd
    assert "costs.total_costs" in fd
