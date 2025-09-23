# Validates: [JSON-11.12], [JSON-11.19]
from __future__ import annotations

from datetime import datetime

from pytest import approx
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def test_brief_includes_cost_model_snapshot_and_aggregates_costs():
    # Two trades with explicit costs
    t1 = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1, 0, 0),
        exit_time=datetime(2024, 1, 1, 1, 0),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
        cost_currency=0.06,
        cost_breakdown={"spread": 0.02, "commission": 0.04, "slippage": 0.0},
    )
    t2 = Trade(
        symbol="Y",
        entry_time=datetime(2024, 1, 2, 0, 0),
        exit_time=datetime(2024, 1, 2, 2, 0),
        entry_price=2.0,
        exit_price=1.9,
        side="short",
        size=2.0,
        pnl=-0.2,
        cost_currency=0.09,
        cost_breakdown={"spread": 0.03, "commission": 0.04, "slippage": 0.02},
    )

    cfg_cost = {
        "spread_per_unit": 0.01,
        "slippage_per_unit": 0.02,
        "commission": {"type": "per_unit", "value": 0.05},
    }

    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[t1, t2],
        initial_cash=1000.0,
        cost_model=cfg_cost,
    )

    # Snapshot of provided cost model
    assert brief["cost_model"] == cfg_cost

    # Aggregates should sum both cost_currency and breakdowns
    costs = brief["costs"]
    assert costs["total_costs"] == approx(0.06 + 0.09)
    assert costs["avg_cost_per_trade"] == approx(0.08)
    assert costs["breakdown"] == {
        "spread": approx(0.02 + 0.03),
        "commission": approx(0.04 + 0.04),
        "slippage": approx(0.0 + 0.02),
    }
