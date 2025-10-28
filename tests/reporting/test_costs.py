# Validates: [JSON-11.12], [JSON-11.19]
from __future__ import annotations

import json
from datetime import datetime, timedelta

from pytest import approx
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief, save_run_brief

from tests.test_helpers import get_empty_global_features_path


def _trade(
    pnl: float,
    ts: datetime,
    symbol: str = "X",
    cost: dict[str, float] | None = None,
) -> Trade:
    cost_breakdown = cost
    cost_currency = sum(cost.values()) if cost else 0.0
    return Trade(
        symbol=symbol,
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1 if pnl >= 0 else 0.9,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
        cost_currency=cost_currency,
        cost_breakdown=cost_breakdown,
    )


def test_trades_include_cost_breakdown_placeholders():
    brief = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[_trade(pnl=10.0, ts=datetime(2023, 1, 1))],
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


def test_brief_includes_cost_model_snapshot_and_aggregates_costs():
    t1 = _trade(
        pnl=0.1,
        ts=datetime(2024, 1, 1, 0, 0),
        cost={"spread": 0.02, "commission": 0.04, "slippage": 0.0},
    )
    t2 = _trade(
        pnl=-0.2,
        ts=datetime(2024, 1, 2, 0, 0),
        symbol="Y",
        cost={"spread": 0.03, "commission": 0.04, "slippage": 0.02},
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

    assert brief["cost_model"] == cfg_cost
    costs = brief["costs"]
    assert costs["total_costs"] == approx(0.06 + 0.09)
    assert costs["avg_cost_per_trade"] == approx(0.08)  # 0.075 rounds up to 0.08
    assert costs["breakdown"] == {
        "spread": approx(0.02 + 0.03),
        "commission": approx(0.04 + 0.04),
        "slippage": approx(0.0 + 0.02),
    }


def test_mixed_trades_breakdown_and_defaults():
    t1 = _trade(
        pnl=0.1,
        ts=datetime(2024, 1, 1),
        symbol="A",
        cost={"spread": 0.02, "commission": 0.03, "slippage": 0.01},
    )
    # Create t2 with explicit cost_currency and no cost breakdown
    t2 = Trade(
        symbol="B",
        entry_time=datetime(2024, 1, 2),
        exit_time=datetime(2024, 1, 2) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=0.9,
        side="short",
        size=1.0,
        pnl=-0.2,
        exit_reason="signal",
        cost_currency=0.05,
        cost_breakdown=None,
    )

    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[t1, t2],
        initial_cash=1000.0,
    )

    trades_json = brief["trades"]
    assert trades_json[0]["cost_breakdown"] == {
        "spread": approx(0.02),
        "commission": approx(0.03),
        "slippage": approx(0.01),
    }
    assert trades_json[1]["cost_breakdown"] == {
        "spread": approx(0.0),
        "commission": approx(0.0),
        "slippage": approx(0.0),
    }

    costs = brief["costs"]
    assert costs["total_costs"] == approx(0.06 + 0.05)
    assert costs["avg_cost_per_trade"] == approx(0.06)  # 0.055 rounds up to 0.06
    assert costs["breakdown"] == {
        "spread": approx(0.02),
        "commission": approx(0.03),
        "slippage": approx(0.01),
    }


def test_save_run_brief_persists_cost_model_and_costs_aggregate(tmp_path):
    run_path = tmp_path / "user" / "run_costs"
    t1 = _trade(
        pnl=0.10,
        ts=datetime(2024, 1, 1),
        symbol="X",
        cost={"spread": 0.02, "commission": 0.04, "slippage": 0.01},
    )
    t2 = _trade(
        pnl=-0.20,
        ts=datetime(2024, 1, 2),
        symbol="Y",
        cost={"spread": 0.03, "commission": 0.01, "slippage": 0.02},
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
    assert data["cost_model"] == cfg_cost
    total_expected = t1.cost_currency + t2.cost_currency
    assert t1.cost_breakdown is not None
    assert t2.cost_breakdown is not None
    breakdown_expected = {
        "spread": t1.cost_breakdown["spread"] + t2.cost_breakdown["spread"],
        "commission": t1.cost_breakdown["commission"] + t2.cost_breakdown["commission"],
        "slippage": t1.cost_breakdown["slippage"] + t2.cost_breakdown["slippage"],
    }
    assert data["costs"]["total_costs"] == approx(total_expected)
    # 0.065 rounds up to 0.07 with ROUND_HALF_UP
    assert data["costs"]["avg_cost_per_trade"] == approx(0.07)
    assert data["costs"]["breakdown"] == {
        "spread": approx(breakdown_expected["spread"]),
        "commission": approx(breakdown_expected["commission"]),
        "slippage": approx(breakdown_expected["slippage"]),
    }
