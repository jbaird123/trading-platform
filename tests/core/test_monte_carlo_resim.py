from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.core.sweeps import monte_carlo_resimulation


def _df() -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(48)]
    close = [1.0 + 0.0008 * ((i % 12) - 6) for i in range(48)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.0006 for c in close],
            "low": [c - 0.0006 for c in close],
            "close": close,
            "volume": [1] * 48,
        },
        index=idx,
    )


def _strategy_cfg() -> dict:
    return {
        "strategy_name": "EMA_Cross_Resim",
        "parameters": {
            "ema_fast_length": 3,
            "ema_slow_length": 7,
        },
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": "${ema_fast_length}"},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": "${ema_slow_length}"},
                "source": "close",
            },
        ],
        "overlays": ["ema_fast", "ema_slow"],
        "long_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_above",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "cross_below",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "short_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_below",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "short_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "cross_above",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
    }


def test_monte_carlo_resimulation_returns_distributions_and_exemplars():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "warmup_bars": 0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"price_offset": 0.002}},
    }
    strat_cfg = _strategy_cfg()
    mc = monte_carlo_resimulation(
        df,
        base_cfg,
        strat_cfg,
        trials=10,
        seed=123,
        mode="bar_bootstrap",
    )
    assert mc["mode"] in {"bar_bootstrap", "bar_resimulation"}
    for key in ["final_equity", "total_pnl", "max_drawdown", "win_rate"]:
        assert key in mc
    assert "risk" in mc and "var_95" in mc["risk"] and "cvar_95" in mc["risk"]
    assert 0.0 <= mc.get("ruin_prob", 0.0) <= 1.0
    assert "exemplars" in mc


def test_monte_carlo_resimulation_with_jitter_and_perturbation():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "warmup_bars": 0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"price_offset": 0.002}},
        "cost_model": {"spread_per_unit": 0.0, "slippage_per_unit": 0.0},
    }
    strat_cfg = _strategy_cfg()
    mc = monte_carlo_resimulation(
        df,
        base_cfg,
        strat_cfg,
        trials=5,
        seed=7,
        mode="bar_bootstrap",
        cost_jitter={
            "spread_jitter_pct": 0.1,
            "slippage_jitter_pct": 0.1,
            "per_trade_cost_jitter_pct": 0.05,
        },
        perturbation={"std_pct": 0.001},
    )
    assert mc["config"]["cost_jitter"]["spread_jitter_pct"] == 0.1
    assert mc["config"]["perturbation"]["std_pct"] == 0.001


def test_monte_carlo_resimulation_block_perturbation():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "warmup_bars": 0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"price_offset": 0.002}},
    }
    strat_cfg = _strategy_cfg()
    mc = monte_carlo_resimulation(
        df,
        base_cfg,
        strat_cfg,
        trials=5,
        seed=9,
        mode="bar_bootstrap",
        perturbation={"mode": "block", "block_len": 5, "std_pct": 0.001},
    )
    assert mc["config"]["perturbation"]["mode"] == "block"
