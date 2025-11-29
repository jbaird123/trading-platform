from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.core.sweeps import walk_forward_optimize_and_test


def _df_wf() -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(40)]
    close = [1.0 + 0.0005 * ((i % 8) - 4) for i in range(40)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.0004 for c in close],
            "low": [c - 0.0004 for c in close],
            "close": close,
            "volume": [1] * 40,
        },
        index=idx,
    )


def _strategy_cfg() -> dict:
    return {
        "strategy_name": "EMA_Cross_WF",
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


def test_walk_forward_optimize_and_test_returns_payload():
    df = _df_wf()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"type": "offset", "price_offset": 0.002}},
        "instrument": {"symbol": "EURUSD", "timeframe": "1H"},
        "data_request": {"symbol": "EURUSD", "timeframe": "1H"},
    }
    strat_cfg = _strategy_cfg()
    out = walk_forward_optimize_and_test(
        df,
        base_cfg,
        strat_cfg,
        window=20,
        step=10,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        objective="pnl_dd_vol",
        dd_penalty=0.5,
        vol_penalty=0.1,
    )
    assert "splits" in out and "oos_total_pnl" in out
    assert out["oos_total_pnl"]["n_splits"] >= 1
