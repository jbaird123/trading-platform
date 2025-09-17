# Validates: [RV-9.2]
from __future__ import annotations

from trading_platform.reporting.compare import compare_briefs


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
