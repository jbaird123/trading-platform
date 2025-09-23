# Validates: [RV-9.4]
from __future__ import annotations

from pathlib import Path

from trading_platform.reporting.compare import compare_briefs
from trading_platform.reporting.compare_html import (
    render_comparison_html,
    save_comparison_html,
)


def _brief(run_id: str, total_pnl: float, name: str = "S") -> dict:
    return {
        "meta": {"run_id": run_id, "strategy_name": name},
        "overall_performance": {
            "total_pnl": total_pnl,
            "mean_pnl": 0.0,
            "win_rate": 0.0,
        },
        "equity_stats": {"max_drawdown": 0.0},
        "costs": {"total_costs": 0.0, "avg_cost_per_trade": 0.0},
        "exposure": {"average_gross_exposure": 0.0, "peak_gross_exposure": 0.0},
    }


def test_render_comparison_html_contains_runs_and_metrics():
    a = _brief("runA", 100.0, name="Alpha")
    b = _brief("runB", 120.0, name="Beta")
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
    a = _brief("runA", 10.0)
    b = _brief("runB", 20.0)
    comp = compare_briefs([a, b])
    out = tmp_path / "cmp.html"
    p = save_comparison_html(out, comp)
    assert p.exists()
    content = p.read_text()
    assert "Comparison Report" in content
    assert "runA" in content and "runB" in content
