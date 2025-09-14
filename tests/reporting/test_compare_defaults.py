from __future__ import annotations

from trading_platform.reporting.compare import compare_briefs


def test_compare_briefs_missing_metrics_defaults_to_zero():
    a = {"meta": {"run_id": "A", "strategy_name": "S"}}
    b = {"meta": {"run_id": "B", "strategy_name": "S"}}
    comp = compare_briefs([a, b])
    # All metrics should exist with zero values
    for k, m in comp["metrics"].items():
        assert m["a"] == 0.0 and m["b"] == 0.0 and m["delta"] == 0.0
