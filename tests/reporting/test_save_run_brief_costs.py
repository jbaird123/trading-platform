from __future__ import annotations

import json
from datetime import datetime, timedelta

from pytest import approx
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import save_run_brief


def _trade(sym: str, start: datetime, pnl: float, cost: dict[str, float]) -> Trade:
    return Trade(
        symbol=sym,
        entry_time=start,
        exit_time=start + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1 if pnl >= 0 else 0.9,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        cost_currency=sum(cost.values()),
        cost_breakdown=cost,
    )


def test_save_run_brief_persists_cost_model_and_costs_aggregate(tmp_path):
    run_path = tmp_path / "user" / "run_costs"
    t1 = _trade(
        "X",
        datetime(2024, 1, 1),
        0.10,
        {"spread": 0.02, "commission": 0.04, "slippage": 0.01},
    )
    t2 = _trade(
        "Y",
        datetime(2024, 1, 2),
        -0.20,
        {"spread": 0.03, "commission": 0.01, "slippage": 0.02},
    )

    cfg_cost = {
        "spread_per_unit": 0.01,
        "slippage_per_unit": 0.02,
        "commission": {"type": "per_unit", "value": 0.05},
    }

    out = save_run_brief(
        run_path,
        meta={"strategy_name": "S", "run_id": "r-costs"},
        params={},
        trades=[t1, t2],
        initial_cash=1000.0,
        cost_model=cfg_cost,
    )

    data = json.loads(out.read_text())
    # Snapshot of cost model should be present
    assert data["cost_model"] == cfg_cost

    # Aggregated costs must match trade inputs
    total_expected = t1.cost_currency + t2.cost_currency
    breakdown_expected = {
        "spread": t1.cost_breakdown["spread"] + t2.cost_breakdown["spread"],
        "commission": t1.cost_breakdown["commission"] + t2.cost_breakdown["commission"],
        "slippage": t1.cost_breakdown["slippage"] + t2.cost_breakdown["slippage"],
    }
    assert data["costs"]["total_costs"] == approx(total_expected)
    assert data["costs"]["avg_cost_per_trade"] == approx(total_expected / 2)
    assert data["costs"]["breakdown"] == {
        "spread": approx(breakdown_expected["spread"]),
        "commission": approx(breakdown_expected["commission"]),
        "slippage": approx(breakdown_expected["slippage"]),
    }
