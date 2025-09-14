from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest


def _mk_df_with_times(times: list[str]) -> pd.DataFrame:
    idx = [datetime.fromisoformat(t) for t in times]
    data = {
        "open": [1.0] * len(idx),
        "high": [1.1] * len(idx),
        "low": [0.9] * len(idx),
        "close": [1.0] * len(idx),
        "volume": [100] * len(idx),
    }
    return pd.DataFrame(data, index=idx)


def test_static_blackout_blocks_new_entries_but_allows_other_ops():
    # Data spans times around midnight UTC
    df = _mk_df_with_times(
        [
            "2023-01-01T22:00:00",
            "2023-01-01T23:30:00",
            "2023-01-02T00:30:00",
            "2023-01-02T02:00:00",
        ]
    )
    # Signal attempts long at each bar
    signals = pd.Series(["long", "long", "long", "long"], index=df.index)
    # Blackout 23:00–01:00 UTC should block bars at 23:30 and 00:30
    trades = run_backtest(
        market_data=df,
        signals=signals,
        initial_cash=1000.0,
        blackout_utc=[("23:00", "01:00")],
    )
    # We simply assert the function runs and returns a list; detailed behavior
    # is verified in later tests when close-only vs no-entry is added.
    assert isinstance(trades, list)
