from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.execution import OandaStubAdapter
from trading_platform.execution.controller import run_live_controller
from trading_platform.portfolio.portfolio import PortfolioManager


def test_controller_flat_desired_continues_loop():
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [1, 1, 1],
            "high": [1, 1, 1],
            "low": [1, 1, 1],
            "close": [1, 1, 1],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    cfg = {
        "strategy_name": "FlatAlways",
        "entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
    }
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    res = run_live_controller(market_data=df, strategy_cfg=cfg, adapter=adapter, pm=pm)
    # No orders placed; reconcile + shutdown logged
    assert res.orders == 0
    assert any(e.get("event") == "reconcile" for e in res.logs)
