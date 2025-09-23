# Validates: [DH-2.11]
from __future__ import annotations

from datetime import datetime

import pandas as pd

from trading_platform.strategy.features import compute_features


def _df():
    return pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5, 4, 3],
            "high": [1.1, 2.1, 3.1, 4.1, 5.1, 4.2, 3.2],
            "low": [0.9, 1.9, 2.9, 3.9, 4.9, 3.8, 2.8],
            "close": [1, 2, 3, 4, 5, 4, 3],
            "volume": [10, 12, 11, 13, 14, 12, 11],
        },
        index=[datetime(2024, 1, 1, i) for i in range(7)],
    )


def test_various_indicators_presence():
    df = _df()
    specs = [
        {"name": "sma3", "type": "SMA", "params": {"length": 3}},
        {"name": "wma3", "type": "WMA", "params": {"length": 3}},
        {"name": "macd", "type": "MACD", "params": {"fast": 3, "slow": 6, "signal": 2}},
        {"name": "psar", "type": "PSAR", "params": {"step": 0.02, "max": 0.2}},
        {"name": "stoch", "type": "STOCH", "params": {"length": 3}},
        {"name": "cci", "type": "CCI", "params": {"length": 3}},
        {"name": "roc", "type": "ROC", "params": {"length": 3}},
        {"name": "kc", "type": "KC", "params": {"length": 3}},
        {"name": "obv", "type": "OBV"},
        {"name": "cmf", "type": "CMF", "params": {"length": 3}},
        {"name": "vwap", "type": "VWAP"},
        {"name": "bb", "type": "BB", "params": {"length": 3, "ndev": 2.0}},
        {"name": "bbw", "type": "BBWidth", "params": {"length": 3, "ndev": 2.0}},
    ]
    out = compute_features(df, specs)
    # Presence assertions
    assert "sma3" in out and "wma3" in out
    assert "macd_macd" in out and "macd_signal" in out and "macd_diff" in out
    assert "psar" in out and "psar_up" in out and "psar_down" in out
    assert "stoch" in out and "stoch_signal" in out
    assert "cci" in out and "roc" in out
    assert "kc_upper" in out and "kc_lower" in out and "kc_middle" in out
    assert "obv" in out and "cmf" in out and "vwap" in out
    assert "bb_upper" in out and "bb_lower" in out and "bb_middle" in out
    assert "bbw" in out
