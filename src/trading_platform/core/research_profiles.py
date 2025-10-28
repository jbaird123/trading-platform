from __future__ import annotations

from typing import Any


def make_research_config(
    *,
    strategy_path: str,
    symbol: str,
    timeframe: str,
    start: str,
    end: str,
    grid: dict[str, list[Any]],
    objective: str = "pnl_dd_vol",
    dd_penalty: float = 0.5,
    vol_penalty: float = 0.1,
    trials: int = 500,
) -> dict[str, Any]:
    """Build a ready-to-run research config dict.

    Minimizes manual edits by producing a config that enables
    parameter_search, walk_forward (skeleton), and monte_carlo.
    """
    return {
        "user_id": "researcher",
        "runs_dir": "runs",
        "initial_cash": 100000,
        "position_size": 25000,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "data_request": {
            "symbol": symbol,
            "timeframe": timeframe,
            "start": start,
            "end": end,
        },
        "strategy_path": strategy_path,
        "rem_path": "config/rem/basic_price_exits.yaml",
        "rmm_path": "config/rmm/daily_trend.yaml",
        "fast_mode": {"limit_bars": 10000},
        "parameter_search": {
            "grid": grid,
            "objective": objective,
            "dd_penalty": dd_penalty,
            "vol_penalty": vol_penalty,
            "seed": 42,
        },
        "walk_forward": {"window": 1000, "step": 250},
        "monte_carlo": {
            "mode": "bar_resimulation",
            "trials": trials,
            "seed": 42,
            "cost_jitter": {
                "spread_jitter_pct": 0.1,
                "slippage_jitter_pct": 0.1,
                "per_trade_cost_jitter_pct": 0.05,
            },
            "perturbation": {"mode": "block", "block_len": 8, "std_pct": 0.001},
        },
    }
