from __future__ import annotations

from datetime import datetime

import pandas as pd
from pytest import approx
from trading_platform.strategy.features import compute_features


def test_hhv_llv_dc_basic():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 2, 1],
            "high": [1, 2, 3, 2, 1],
            "low": [1, 2, 3, 2, 1],
            "close": [1, 2, 3, 2, 1],
            "volume": [1, 1, 1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(5)],
    )
    specs = [
        {"name": "hhv3", "type": "HHV", "params": {"length": 3}, "source": "high"},
        {"name": "llv2", "type": "LLV", "params": {"length": 2}, "source": "low"},
        {"name": "dc5", "type": "DC", "params": {"length": 5}},
    ]
    out = compute_features(df, specs)
    assert out["hhv3"].iloc[-1] == approx(3.0)
    assert out["llv2"].iloc[-1] == approx(1.0)
    assert "dc5_upper" in out and "dc5_lower" in out
