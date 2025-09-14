from __future__ import annotations

from pytest import approx, raises
from trading_platform.reporting.compare import compare_briefs


def _brief(
    run_id: str,
    total_pnl: float,
    mean_pnl: float,
    win_rate: float,
    max_dd: float,
    total_costs: float,
    avg_cost: float,
    avg_exp: float,
    peak_exp: float,
    strategy_name: str = "S",
) -> dict:
    return {
        "meta": {"run_id": run_id, "strategy_name": strategy_name},
        "overall_performance": {
            "total_pnl": total_pnl,
            "mean_pnl": mean_pnl,
            "win_rate": win_rate,
        },
        "equity_stats": {"max_drawdown": max_dd},
        "costs": {"total_costs": total_costs, "avg_cost_per_trade": avg_cost},
        "exposure": {
            "average_gross_exposure": avg_exp,
            "peak_gross_exposure": peak_exp,
        },
    }


def test_compare_briefs_two_runs_schema_and_deltas():
    a = _brief(
        "A",
        total_pnl=100.0,
        mean_pnl=10.0,
        win_rate=0.6,
        max_dd=50.0,
        total_costs=5.0,
        avg_cost=0.5,
        avg_exp=1000.0,
        peak_exp=1500.0,
    )
    b = _brief(
        "B",
        total_pnl=120.0,
        mean_pnl=12.0,
        win_rate=0.65,
        max_dd=40.0,
        total_costs=4.0,
        avg_cost=0.4,
        avg_exp=900.0,
        peak_exp=1400.0,
    )

    out = compare_briefs([a, b])
    assert out["runs"][0]["run_id"] == "A"
    assert out["runs"][1]["run_id"] == "B"
    m = out["metrics"]
    assert m["total_pnl"]["a"] == approx(100.0)
    assert m["total_pnl"]["b"] == approx(120.0)
    assert m["total_pnl"]["delta"] == approx(20.0)
    # Improvement in drawdown is negative delta (b - a)
    assert m["max_drawdown"]["delta"] == approx(40.0 - 50.0)
    # Costs decreased
    assert m["total_costs"]["delta"] == approx(4.0 - 5.0)
    # Exposure deltas computed
    assert m["average_gross_exposure"]["delta"] == approx(900.0 - 1000.0)


def test_compare_briefs_requires_two():
    with raises(ValueError):
        compare_briefs([])
    with raises(ValueError):
        compare_briefs([_brief("A", 0, 0, 0, 0, 0, 0, 0, 0)])
