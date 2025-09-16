from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest

from tests.backtester.dummy_objects import _dummy_strategy_with_sl


def test_daily_loss_cap_blocks_new_entries_after_loss():
    # 3 bars same day; first trade loses on bar 1 via stop; block entry on bar 2
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [100.0, 89.0, 100.0],
            "high": [101.0, 95.0, 101.0],
            "low": [99.0, 89.0, 99.0],
            "close": [100.0, 90.0, 100.0],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    # Signals: enter long at bar 0 and bar 2
    sig = pd.Series(["long", "flat", "long"], index=df.index)
    trades, _, skipped = run_backtest(
        df,
        sig,
        strategy=_dummy_strategy_with_sl(10.0),
        return_exposure=True,
        return_skips=True,
        daily_loss_cap=5.0,
    )
    # First trade loses 10 (stop at 90), then bar 2 attempt is skipped by cap
    assert len(trades) == 1
    assert any(s.get("reason_code") == "risk_cap" for s in skipped)
