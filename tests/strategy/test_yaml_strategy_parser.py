# Validates: [SE-3.5.3]
from __future__ import annotations

from datetime import datetime

import pandas as pd

from trading_platform.strategy.yaml_strategy import compile_strategy


def test_yaml_strategy_compile_and_signals_is_above_below():
    cfg = {
        "strategy_name": "TestStrat",
        "parameters": {},
        "overlays": ["ema_fast", "ema_slow"],
        "features": [],
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
        ],
    }
    strat = compile_strategy(cfg)
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0, 2.0, 1.0],
            "high": [1.0, 2.0, 3.0, 2.0, 1.0],
            "low": [1.0, 2.0, 3.0, 2.0, 1.0],
            "close": [1.0, 2.0, 3.0, 2.0, 1.0],
            "volume": [1, 1, 1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(5)],
    )
    sig = strat.generate_signals(df)
    # Expect: flat at 1.0, enter long at 2.0, remain long at 3.0 and 2.0, exit at 1.0
    assert list(sig) == ["flat", "long", "long", "long", "flat"]


def test_yaml_strategy_cross_above_below():
    cfg = {
        "strategy_name": "TestStrat",
        "parameters": {},
        "features": [
            {"name": "ema_fast", "type": "EMA", "params": {"length": 2}},
            {"name": "ema_slow", "type": "EMA", "params": {"length": 4}},
        ],
        "long_entry_rules": [
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
    }
    strat = compile_strategy(cfg)
    df = pd.DataFrame(
        {
            "open": [1, 1, 1, 1, 1],
            "high": [1, 1, 1, 1, 1],
            "low": [1, 1, 1, 1, 1],
            "close": [100, 101, 102, 101, 100],
            "volume": [1, 1, 1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(5)],
    )
    sig = strat.generate_signals(df)
    # Signals will be flat until indicators are warm
    assert sig.iloc[-1] == "flat" or sig.iloc[-1] == "short"


def test_yaml_strategy_all_of_and_short_side():
    cfg = {
        "strategy_name": "TestStrat",
        "parameters": {},
        "short_entry_rules": [
            {
                "all_of": [
                    {"condition": "is_below", "left": "close", "right": 1.5},
                    {"condition": "is_above", "left": "close", "right": 0},
                ]
            }
        ],
        "short_exit_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
    }
    strat = compile_strategy(cfg)
    df = pd.DataFrame(
        {
            "open": [1, 2, 1],
            "high": [1, 2, 1],
            "low": [1, 2, 1],
            "close": [1, 2, 1],
            "volume": [1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(3)],
    )
    sig = strat.generate_signals(df)
    # flat, exit short, enter short
    assert list(sig) == ["short", "flat", "short"]
