from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_brief_schema_accepts_mc_wf_ps_enumerated_fields():
    schema_path = Path("docs/schemas/brief.schema.json")
    schema = json.loads(schema_path.read_text())
    brief = {
        "meta": {"run_id": "r", "strategy_name": "S"},
        "strategy_params": {},
        "overall_performance": {
            "n_trades": 0,
            "total_pnl": 0.0,
            "mean_pnl": 0.0,
            "median_pnl": 0.0,
            "by_side_total_pnl": {"long": 0.0, "short": 0.0},
            "win_rate": 0.0,
            "initial_equity": 1000.0,
            "final_equity": 1000.0,
        },
        "risk_snapshot": {
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
        },
        "equity_stats": {
            "equity_curve": [["2024-01-01T00:00:00", 1000.0]],
            "drawdown_curve": [["2024-01-01T00:00:00", 0.0]],
            "max_drawdown": 0.0,
            "dd_duration_bars": 0,
        },
        "distribution": {
            "pnl_mean": 0.0,
            "pnl_median": 0.0,
            "pnl_std": 0.0,
            "p05": 0.0,
            "p95": 0.0,
        },
        "streaks": {
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
            "current_streak": 0,
        },
        "holding_time": {"median_secs": 0.0},
        "costs": {
            "total_costs": 0.0,
            "avg_cost_per_trade": 0.0,
            "breakdown": {"spread": 0.0, "commission": 0.0, "slippage": 0.0},
        },
        "trades": [],
        "monte_carlo": {
            "mode": "bar_resimulation",
            "trials": 10,
            "config": {"cost_jitter": {}, "perturbation": {}},
            "final_equity": {"mean": 1000.0, "p05": 900.0, "p95": 1100.0},
            "total_pnl": {"mean": 0.0, "p05": -100.0, "p95": 100.0},
            "max_drawdown": {"mean": 10.0, "p05": 5.0, "p95": 20.0},
            "win_rate": {"mean": 0.5, "p05": 0.2, "p95": 0.8},
            "risk": {"var_95": -100.0, "cvar_95": -150.0},
            "ruin_prob": 0.0,
            "time_under_water_mean": 0.2,
            "exemplars": {
                "worst": {"final_equity": 900.0, "curve": [1000.0, 900.0]},
                "median": {"final_equity": 1000.0, "curve": [1000.0, 1000.0]},
                "best": {"final_equity": 1100.0, "curve": [1000.0, 1100.0]},
            },
        },
        "walk_forward": {
            "splits": [{"train_start": "t1", "test_start": "t2", "oos_score": 0.0}],
            "oos_total_pnl": {"mean": 0.0, "median": 0.0, "n_splits": 1},
        },
        "parameter_search": {
            "top": {"params": {"x": 1}, "score": 1.0},
            "results": [{"params": {"x": 1}, "score": 1.0}],
        },
    }
    jsonschema.validate(instance=brief, schema=schema)
