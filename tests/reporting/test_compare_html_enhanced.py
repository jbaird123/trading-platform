# Validates: [RV-9.4]
from __future__ import annotations

from trading_platform.reporting.compare import compare_briefs
from trading_platform.reporting.compare_html import render_comparison_html


def _brief(run_id: str, total_pnl: float) -> dict:
    return {
        "meta": {"run_id": run_id, "strategy_name": run_id},
        "overall_performance": {"total_pnl": total_pnl, "mean_pnl": 0.0},
        "equity_stats": {"max_drawdown": 0.0},
        "costs": {"total_costs": 0.0, "avg_cost_per_trade": 0.0},
        "exposure": {"average_gross_exposure": 0.0, "peak_gross_exposure": 0.0},
    }


def test_compare_html_has_sortable_headers_and_best_highlight():
    a = _brief("A", 10.0)
    b = _brief("B", 25.0)
    comp = compare_briefs([a, b])
    html = render_comparison_html(comp)
    assert "onclick='sortTable(3)'" in html  # sortable delta header
    # Expect a highlighted best delta cell
    assert "class='best'" in html
