from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.strategy.yaml_strategy import compile_strategy


def test_yaml_strategy_compile_and_signals_is_above_below():
    cfg = {
        "strategy_name": "TestStrat",
        "overlays": ["ema_fast", "ema_slow"],
        "features": [],
        "entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
        "exit_rules": [
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
