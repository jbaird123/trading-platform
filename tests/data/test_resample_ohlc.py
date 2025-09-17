# Validates: [DH-2.5]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.data.schema import resample_ohlc


def test_resample_ohlc_rules_hour_to_2h():
    idx = [datetime(2024, 1, 1, h) for h in range(4)]
    df = pd.DataFrame(
        {
            "open": [10, 12, 14, 16],
            "high": [11, 13, 15, 17],
            "low": [9, 11, 13, 15],
            "close": [10.5, 12.5, 14.5, 16.5],
            "volume": [1, 2, 3, 4],
        },
        index=idx,
    )
    out = resample_ohlc(df, "2h")
    # First 2h bucket
    row0 = out.iloc[0]
    assert row0["open"] == 10
    assert row0["high"] == 13
    assert row0["low"] == 9
    assert row0["close"] == 12.5
    assert row0["volume"] == 3
    # Second 2h bucket
    row1 = out.iloc[1]
    assert row1["open"] == 14
    assert row1["high"] == 17
    assert row1["low"] == 13
    assert row1["close"] == 16.5
    assert row1["volume"] == 7
