from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.backtester.core import run_backtest


def _mk_df(n: int) -> pd.DataFrame:
    start = datetime(2023, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(n)]
    data = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100}
    return pd.DataFrame([data] * n, index=idx)


def test_warmup_delays_first_entry_until_threshold():
    # 5 bars hourly, warmup of 3 bars → first entry allowed at index 3 (4th bar)
    df = _mk_df(5)
    # Signals: long on first 4 bars, flat on last bar to force close
    sig = pd.Series(["long", "long", "long", "long", "flat"], index=df.index)
    trades = run_backtest(
        market_data=df,
        signals=sig,
        initial_cash=1000.0,
        warmup_bars=3,
    )
    # One completed trade: entry at 4th bar, exit on 5th due to flat
    assert len(trades) == 1
    assert trades[0].entry_time == df.index[3]


def test_no_warmup_allows_immediate_entry():
    df = _mk_df(3)
    sig = pd.Series(["long", "flat", "flat"], index=df.index)
    trades = run_backtest(
        market_data=df,
        signals=sig,
        initial_cash=1000.0,
        warmup_bars=0,
    )
    # First trade should enter at the first bar
    assert len(trades) == 1
    assert trades[0].entry_time == df.index[0]
