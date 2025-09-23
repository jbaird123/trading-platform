# Validates: [JSON-11.12]
from __future__ import annotations

from datetime import datetime, timedelta

from pytest import approx

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def test_mixed_trades_breakdown_and_defaults():
    # t1 has explicit breakdown; t2 lacks breakdown (None) but has a total cost
    t1 = Trade(
        symbol="A",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
        cost_currency=0.06,
        cost_breakdown={"spread": 0.02, "commission": 0.03, "slippage": 0.01},
    )
    t2 = Trade(
        symbol="B",
        entry_time=datetime(2024, 1, 2),
        exit_time=datetime(2024, 1, 2) + timedelta(hours=1),
        entry_price=2.0,
        exit_price=1.9,
        side="short",
        size=2.0,
        pnl=-0.2,
        cost_currency=0.05,
        cost_breakdown=None,
    )

    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[t1, t2],
        initial_cash=1000.0,
    )

    # Trades serialization: t2 should get zero placeholders for breakdown
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

    # Aggregates: totals include both trades' cost_currency; breakdown sums only from t1
    costs = brief["costs"]
    assert costs["total_costs"] == approx(0.06 + 0.05)
    assert costs["avg_cost_per_trade"] == approx(0.06)
    assert costs["breakdown"] == {
        "spread": approx(0.02),
        "commission": approx(0.03),
        "slippage": approx(0.01),
    }
