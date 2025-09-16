from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest

from tests.backtester.dummy_objects import _dummy_strategy_cfg


def test_position_cap_skips_same_direction_when_already_open():
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [1, 1],
        },
        index=idx,
    )
    sig = pd.Series(["long", "long"], index=df.index)
    trades, _, skipped = run_backtest(
        df, sig, strategy=_dummy_strategy_cfg(), return_exposure=True, return_skips=True
    )
    # With constant prices and no exits, there are no closed trades yet.
    # Second long should be skipped due to position_cap.
    assert len(trades) == 0
    assert any(s.get("reason_code") == "position_cap" for s in skipped)
