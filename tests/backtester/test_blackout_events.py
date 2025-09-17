# Validates: [SYS-1.5.2]
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg


def _mk_df(start: datetime, n: int, step_minutes: int = 60) -> pd.DataFrame:
    idx = [start + timedelta(minutes=i * step_minutes) for i in range(n)]
    data = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100}
    return pd.DataFrame([data] * n, index=idx)


def test_event_blackout_blocks_new_entries():
    start = datetime(2023, 1, 1, 10, 0)
    df = _mk_df(start, 4, 60)
    signals = pd.Series(["long", "long", "long", "long"], index=df.index)

    ev = {"start": datetime(2023, 1, 1, 11, 0), "end": datetime(2023, 1, 1, 12, 30)}
    config = RunConfig(initial_cash=1000.0, blackout_events=[ev])
    rem = RiskExitManager(config={})
    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
    )

    assert isinstance(trades, list)
