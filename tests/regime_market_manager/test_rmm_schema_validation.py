from __future__ import annotations

import pytest
from trading_platform.regime_market_manager.config import validate_rmm_config


def test_rmm_validation_accepts_minimal_valid():
    cfg = {
        "regimes": [
            {
                "label": "trend_up",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [{"condition": "is_above", "left": 10, "right": 5}]
                },
            }
        ]
    }
    validate_rmm_config(cfg)


def test_rmm_validation_rejects_missing_regimes():
    with pytest.raises(ValueError) as e:
        validate_rmm_config({})
    assert "regimes" in str(e.value)
