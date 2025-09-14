from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.strategy.features import compute_features


def test_dc_vwap_and_unknown_type():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4],
            "high": [2, 3, 4, 5],
            "low": [1, 2, 2, 3],
            "close": [1.5, 2.5, 3.5, 4.5],
            "volume": [10, 10, 10, 10],
        },
        index=[datetime(2024, 1, 1, i) for i in range(4)],
    )
    specs = [
        {"name": "dc", "type": "DC", "params": {"length": 2}},
        {"name": "vwap", "type": "VWAP"},
        {"name": "unknown", "type": "UNKNOWN"},
    ]
    out = compute_features(df, specs)
    assert "dc_upper" in out and "dc_lower" in out
    assert "vwap" in out
    assert "unknown" in out  # present (pd.NA)
