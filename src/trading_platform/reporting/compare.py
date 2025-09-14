from __future__ import annotations

from typing import Any


def _pick(d: dict[str, Any], path: list[str], default: float = 0.0) -> float:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


def compare_briefs(briefs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare two briefs and return metric deltas.

    For now supports exactly two briefs. Returns a dict:
      {
        "runs": [{"run_id": ..., "strategy_name": ...}, ...],
        "metrics": {
          "total_pnl": {"a": 0.0, "b": 1.0, "delta": 1.0},
          ...
        }
      }
    """
    if len(briefs) != 2:
        raise ValueError("compare_briefs expects exactly two briefs")
    a, b = briefs
    run_a = {
        "run_id": a.get("meta", {}).get("run_id"),
        "strategy_name": a.get("meta", {}).get("strategy_name"),
    }
    run_b = {
        "run_id": b.get("meta", {}).get("run_id"),
        "strategy_name": b.get("meta", {}).get("strategy_name"),
    }

    metric_paths = {
        "total_pnl": ["overall_performance", "total_pnl"],
        "mean_pnl": ["overall_performance", "mean_pnl"],
        "win_rate": ["overall_performance", "win_rate"],
        "max_drawdown": ["equity_stats", "max_drawdown"],
        "total_costs": ["costs", "total_costs"],
        "avg_cost_per_trade": ["costs", "avg_cost_per_trade"],
        "average_gross_exposure": ["exposure", "average_gross_exposure"],
        "peak_gross_exposure": ["exposure", "peak_gross_exposure"],
    }
    metrics: dict[str, dict[str, float]] = {}
    for name, path in metric_paths.items():
        va = _pick(a, path)
        vb = _pick(b, path)
        metrics[name] = {"a": va, "b": vb, "delta": vb - va}

    return {"runs": [run_a, run_b], "metrics": metrics}
