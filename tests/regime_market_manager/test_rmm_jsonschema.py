# Validates: [RMM-4.9]
from __future__ import annotations

import pytest

from trading_platform.regime_market_manager.config import validate_rmm_config


def test_rmm_jsonschema_validates_required_fields():
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


def test_rmm_jsonschema_missing_regimes_errors():
    with pytest.raises(ValueError) as e:
        validate_rmm_config({})
    assert "rmm schema" in str(e.value) or "regimes" in str(e.value)
