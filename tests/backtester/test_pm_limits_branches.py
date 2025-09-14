from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest


def _df():
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    return pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [1, 1],
        },
        index=idx,
    )


def test_cap_not_reached_no_skip_when_already_open():
    df = _df()
    sig = pd.Series(["long", "long"], index=df.index)
    trades, _, skipped = run_backtest(
        df, sig, pm_limits={"max_open_long": 2}, return_exposure=True, return_skips=True
    )
    # No skip due to cap; still no closed trades with flat prices
    assert len(trades) == 0
    assert not any(s.get("reason_code") == "position_cap" for s in skipped)


def test_cap_zero_blocks_new_entry():
    df = _df()
    sig = pd.Series(["long", "long"], index=df.index)
    trades, _, skipped = run_backtest(
        df, sig, pm_limits={"max_open_long": 0}, return_exposure=True, return_skips=True
    )
    # First attempt skipped due to cap 0
    assert any(s.get("reason_code") == "position_cap" for s in skipped)
