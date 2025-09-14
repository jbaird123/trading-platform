from __future__ import annotations

from trading_platform.regime_market_manager.config import validate_rmm_config


def test_rmm_validation_accepts_any_of_minimal_valid():
    cfg = {
        "regimes": [
            {
                "label": "range",
                "confidence": 0.5,
                "conditions": {
                    "any_of": [{"condition": "is_below", "left": 10, "right": 20}]
                },
            }
        ]
    }
    validate_rmm_config(cfg)
