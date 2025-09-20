from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.core.sweeps import run_parameter_sweep


def _df() -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(60)]
    # Simple wave to induce a few crosses
    close = [1.0 + 0.001 * ((i % 10) - 5) for i in range(60)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.0005 for c in close],
            "low": [c - 0.0005 for c in close],
            "close": close,
            "volume": [1] * 60,
        },
        index=idx,
    )


def _strategy_cfg() -> dict:
    return {
        "strategy_name": "EMA_Cross_Test",
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


def test_run_parameter_sweep_returns_top_and_results():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "warmup_bars": 0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"price_offset": 0.002}},
    }
    strat_cfg = _strategy_cfg()
    out = run_parameter_sweep(
        df,
        base_cfg,
        strat_cfg,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        seed=123,
        objective="total_pnl",
    )
    assert "top" in out and "results" in out
    assert len(out["results"]) == 4
    assert set(out["results"][0].keys()) == {"params", "score"}


def test_parameter_sweep_pnl_minus_dd_objective():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "warmup_bars": 0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"price_offset": 0.002}},
    }
    strat_cfg = _strategy_cfg()
    out = run_parameter_sweep(
        df,
        base_cfg,
        strat_cfg,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        objective="pnl_minus_dd",
        dd_penalty=0.5,
    )
    assert "top" in out and "results" in out


def test_parameter_sweep_pnl_dd_vol_objective():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "warmup_bars": 0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"price_offset": 0.002}},
    }
    strat_cfg = _strategy_cfg()
    out = run_parameter_sweep(
        df,
        base_cfg,
        strat_cfg,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        objective="pnl_dd_vol",
        dd_penalty=0.5,
        vol_penalty=0.1,
    )
    assert "top" in out and "results" in out
