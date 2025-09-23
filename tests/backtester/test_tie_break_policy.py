# Validates: [BT-7.6]
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from tests.backtester.dummy_objects import _dummy_strategy_with_sl_tp
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager


@pytest.mark.req_BT_7_6
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
    config = RunConfig(
        rem_config={
            "stop_loss": {"absolute_price": 95.0},
            "take_profit": {"absolute_price": 105.0},
        }
    )
    rem = RiskExitManager(config=config.rem_config)
    trades = run_backtest(
        df,
        sig,
        strategy=_dummy_strategy_with_sl_tp(95.0, 105.0),
        config=config,
        rem=rem,
    )
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_price == 95.0 and t.exit_reason == "stop-loss"
