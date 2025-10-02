# Validates: [RV-9.2], [RV-9.4], [SYS-1.4.1], [SYS-1.4.2], [SYS-1.4.3]
from __future__ import annotations

import json
from pathlib import Path

from pytest import approx, raises
from trading_platform.reporting.compare import compare_briefs
from trading_platform.reporting.compare_html import (
    render_comparison_html,
    save_comparison_html,
    save_comparison_report,
)


def _brief(
    run_id: str,
    total_pnl: float,
    mean_pnl: float = 0.0,
    win_rate: float = 0.0,
    max_dd: float = 0.0,
    total_costs: float = 0.0,
    avg_cost: float = 0.0,
    avg_exp: float = 0.0,
    peak_exp: float = 0.0,
    strategy_name: str | None = None,
) -> dict:
    if strategy_name is None:
        strategy_name = f"S-{run_id}"
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
        strategy_name="S",
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
        strategy_name="S",
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
        compare_briefs([_brief("A", 0, strategy_name="S")])


def test_compare_briefs_missing_metrics_defaults_to_zero():
    a = {"meta": {"run_id": "A", "strategy_name": "S"}}
    b = {"meta": {"run_id": "B", "strategy_name": "S"}}
    comp = compare_briefs([a, b])
    # All metrics should exist with zero values
    for k, m in comp["metrics"].items():
        assert m["a"] == 0.0 and m["b"] == 0.0 and m["delta"] == 0.0


def test_render_comparison_html_contains_runs_and_metrics():
    a = _brief("runA", 100.0, strategy_name="Alpha")
    b = _brief("runB", 120.0, strategy_name="Beta")
    comp = compare_briefs([a, b])
    html = render_comparison_html(comp)
    assert "Comparison Report" in html
    assert "Alpha" in html and "runA" in html
    assert "Beta" in html and "runB" in html
    # Check a metric row renders with delta 20
    assert "Delta (B - A)" in html
    assert ">100<" in html or ">100.0<" in html  # A total_pnl
    assert ">120<" in html or ">120.0<" in html  # B total_pnl


def test_save_comparison_html_writes_file(tmp_path: Path):
    a = _brief("runA", 10.0, strategy_name="S")
    b = _brief("runB", 20.0, strategy_name="S")
    comp = compare_briefs([a, b])
    out = tmp_path / "cmp.html"
    p = save_comparison_html(out, comp)
    assert p.exists()
    content = p.read_text()
    assert "Comparison Report" in content
    assert "runA" in content and "runB" in content


def test_compare_html_has_sortable_headers_and_best_highlight():
    a = _brief("A", 10.0)
    b = _brief("B", 25.0)
    comp = compare_briefs([a, b])
    html = render_comparison_html(comp)
    assert "onclick='sortTable(3)'" in html  # sortable delta header
    # Expect a highlighted best delta cell
    assert "class='best'" in html


def test_compare_briefs_non_numeric_values_default_to_zero():
    a = {
        "meta": {"run_id": "A", "strategy_name": "S"},
        "overall_performance": {"total_pnl": "x"},
    }
    b = {
        "meta": {"run_id": "B", "strategy_name": "S"},
        "overall_performance": {"total_pnl": "y"},
    }
    comp = compare_briefs([a, b])
    m = comp["metrics"]["total_pnl"]
    assert m["a"] == 0.0 and m["b"] == 0.0 and m["delta"] == 0.0


def test_save_comparison_report_reads_briefs_and_writes_html(tmp_path: Path):
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(json.dumps(_brief("A", 0.0)))
    b_path.write_text(json.dumps(_brief("B", 0.0)))

    out = tmp_path / "report.html"
    p = save_comparison_report(a_path, b_path, out)
    assert p.exists()
    content = p.read_text()
    assert "Comparison Report" in content
    assert "S-A" in content and "S-B" in content
