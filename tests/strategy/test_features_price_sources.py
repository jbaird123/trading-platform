from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.strategy.features import compute_features


def test_price_sources_hl2_ohlc4_and_source_ref():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [3, 4, 5],
            "low": [1, 2, 3],
            "close": [2, 3, 4],
            "volume": [1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(3)],
    )
    specs = [
        {"name": "ema_hl2", "type": "EMA", "params": {"length": 1}, "source": "hl2"},
        {
            "name": "ema_ohlc4",
            "type": "EMA",
            "params": {"length": 1},
            "source": "ohlc4",
        },
    ]
    out = compute_features(df, specs)
    assert "ema_hl2" in out and "ema_ohlc4" in out
