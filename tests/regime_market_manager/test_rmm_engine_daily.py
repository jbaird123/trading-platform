from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.regime_market_manager.engine import RMMEngine


def _mk_hourly(n: int) -> pd.DataFrame:
    start = datetime(2023, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(n)]
    # Simple rising then falling close to trigger regime switches
    close = [100 + i * 0.1 for i in range(n)]
    df = pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1] * n,
        },
        index=idx,
    )
    return df


def test_rmm_engine_classify_daily_basic():
    cfg = {
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": 3},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": 5},
                "source": "close",
            },
            {"name": "adx", "type": "ADX", "params": {"length": 5}},
        ],
        "regimes": [
            {
                "label": "trend_up",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"ref": "ema_fast"},
                            "right": {"ref": "ema_slow"},
                        },
                    ]
                },
            },
            {
                "label": "trend_down",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_below",
                            "left": {"ref": "ema_fast"},
                            "right": {"ref": "ema_slow"},
                        },
                    ]
                },
            },
        ],
    }
    engine = RMMEngine(config=cfg)
    # Validate does not raise
    RMMEngine.validate_config(cfg)

    df = _mk_hourly(48)  # 2 days hourly
    daily = engine.classify_daily(df)
    assert set(daily.columns) == {"label", "confidence"}
    assert len(daily) >= 1
    # All confidences between 0..1
    assert (daily["confidence"] >= 0).all() and (daily["confidence"] <= 1).all()
