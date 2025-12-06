from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.core.sweeps import walk_forward_optimize_and_test


def _df_wf() -> pd.DataFrame:
    # Create enough data for walk forward with EMA warmup built-in
    # EMA slow length is 9, so we need at least 10 bars for warmup
    # Total: 100 bars gives enough room for multiple walk-forward splits
    # Start 12 hours early to ensure EMAs are populated by the trading start
    start = datetime(2023, 12, 31, 12)
    idx = pd.date_range(start, periods=100, freq="1h", tz="UTC")
    close = [1.0 + 0.0005 * ((i % 8) - 4) for i in range(len(idx))]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.0004 for c in close],
            "low": [c - 0.0004 for c in close],
            "close": close,
            "volume": [1] * len(idx),
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
        "data_request": {"symbol": "EURUSD", "timeframe": "1H", "start": "2024-01-01"},
    }
    strat_cfg = _strategy_cfg()
    # Use visible_start to skip the first few bars needed for EMA warmup
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
        visible_start=pd.Timestamp("2024-01-01T10:00:00", tz="UTC"),  # After EMA warmup
    )
    assert "splits" in out and "oos_total_pnl" in out
    assert out["oos_total_pnl"]["n_splits"] >= 1
