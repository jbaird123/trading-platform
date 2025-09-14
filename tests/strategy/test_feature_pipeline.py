from __future__ import annotations

import pandas as pd
from pytest import approx
from trading_platform.strategy.features import compute_features


def test_compute_features_basic_indicators():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [1.1, 2.1, 3.1, 4.1, 5.1],
            "low": [0.9, 1.9, 2.9, 3.9, 4.9],
            "close": [1, 2, 3, 4, 5],
            "volume": [1, 1, 1, 1, 1],
        }
    )
    specs = [
        {"name": "ema2", "type": "EMA", "params": {"length": 2}, "source": "close"},
        {"name": "rsi2", "type": "RSI", "params": {"length": 2}, "source": "close"},
        {"name": "atr2", "type": "ATR", "params": {"length": 2}},
    ]
    out = compute_features(df, specs)
    assert "ema2" in out and "rsi2" in out and "atr2" in out
    # EMA(2) last value should be near 4.5 (EWM span=2)
    assert out["ema2"].iloc[-1] == approx(4.5, abs=0.1)
    # RSI is bounded [0,100]
    assert 0.0 <= float(out["rsi2"].iloc[-1]) <= 100.0
    # ATR positive
    assert float(out["atr2"].iloc[-1]) >= 0.0
