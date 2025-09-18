# ORPHANED_TEST: This test does not seem to correspond to a requirement.
from __future__ import annotations

from trading_platform.strategy.yaml_strategy import compile_strategy


def test_feature_params_resolve_from_named_parameters():
    cfg = {
        "strategy_name": "ParamBinding",
        "parameters": {"ema_fast_len": 10, "ema_slow_len": 21},
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": "${ema_fast_len}"},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": "ema_slow_len"},
                "source": "close",
            },
        ],
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0}]}
        ],
    }
    s = compile_strategy(cfg)
    feats = {f["name"]: f for f in s.features}
    assert feats["ema_fast"]["params"]["length"] == 10
    assert feats["ema_slow"]["params"]["length"] == 21
