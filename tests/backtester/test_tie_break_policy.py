from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest

from tests.backtester.dummy_objects import _dummy_strategy_cfg


def test_tie_break_stop_then_tp_for_long():
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [100.0, 105.0],
            "low": [100.0, 95.0],
            "close": [100.0, 100.0],
            "volume": [1, 1],
        },
        index=idx,
    )
    sig = pd.Series(["long", "flat"], index=df.index)
    trades = run_backtest(
        df,
        sig,
        strategy=_dummy_strategy_cfg(),
        stop_loss=5.0,
        take_profit=5.0,
    )
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_price == 95.0 and t.exit_reason == "stop-loss"
