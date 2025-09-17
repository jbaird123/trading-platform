# Validates: [JSON-11.25]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def test_r_multiple_serialized_in_trades_with_placeholder_when_missing():
    t_with = Trade(
        symbol="A",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.2,
        side="long",
        size=1.0,
        pnl=0.2,
        r_multiple=2.0,
    )
    t_without = Trade(
        symbol="B",
        entry_time=datetime(2024, 1, 2),
        exit_time=datetime(2024, 1, 2) + timedelta(hours=1),
        entry_price=2.0,
        exit_price=1.9,
        side="short",
        size=1.0,
        pnl=-0.1,
    )
    brief = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[t_with, t_without],
        initial_cash=1000.0,
    )
    tr = brief["trades"]
    assert tr[0]["r_multiple"] == 2.0
    assert tr[1]["r_multiple"] is None
