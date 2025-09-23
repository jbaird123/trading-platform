# Validates: [SYS-1.3.2]
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from tests.backtester.dummy_objects import _dummy_strategy_cfg
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager


def _mk_df() -> pd.DataFrame:
    idx = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(3)]
    data = {
        "open": [1.0, 1.1, 1.2],
        "high": [1.1, 1.2, 1.3],
        "low": [0.9, 1.0, 1.1],
        "close": [1.0, 1.15, 1.25],
        "volume": [100, 100, 100],
    }
    df = pd.DataFrame(data, index=idx)
    return df


def test_run_backtest_accepts_instrument_snapshot():
    df = _mk_df()
    signals = pd.Series(["flat", "long", "flat"], index=df.index)
    instr = {"symbol": "EUR_USD", "tick_size": 0.0001}
    config = RunConfig(initial_cash=1000.0, allow_flip_on_bar=False, instrument=instr)
    rem = RiskExitManager(config={})
    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
    )
    # Still produces trades as usual; instrument is accepted without side effects
    assert isinstance(trades, list)
