# Validates: [RV-9.4]
from __future__ import annotations

import json
from pathlib import Path

from trading_platform.reporting.compare_html import save_comparison_report


def _brief(run_id: str) -> dict:
    return {
        "meta": {"run_id": run_id, "strategy_name": f"S-{run_id}"},
        "overall_performance": {"total_pnl": 0.0, "mean_pnl": 0.0, "win_rate": 0.0},
        "equity_stats": {"max_drawdown": 0.0},
        "costs": {"total_costs": 0.0, "avg_cost_per_trade": 0.0},
        "exposure": {"average_gross_exposure": 0.0, "peak_gross_exposure": 0.0},
    }


def test_save_comparison_report_reads_briefs_and_writes_html(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(_brief("A")))
    b.write_text(json.dumps(_brief("B")))

    out = tmp_path / "report.html"
    p = save_comparison_report(a, b, out)
    assert p.exists()
    content = p.read_text()
    assert "Comparison Report" in content
    assert "S-A" in content and "S-B" in content
