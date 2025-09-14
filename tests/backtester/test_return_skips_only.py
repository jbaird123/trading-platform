from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest


def test_return_skips_without_exposure():
    idx = [datetime(2024, 1, 1, h) for h in range(1)]
    df = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}, index=idx
    )
    sig = pd.Series(["long"], index=df.index)
    trades, exposure, skipped = run_backtest(
        df, sig, return_exposure=False, return_skips=True
    )
    assert exposure == [] and isinstance(skipped, list)
