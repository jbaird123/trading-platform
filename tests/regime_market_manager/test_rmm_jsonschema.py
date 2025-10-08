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


def test_rmm_jsonschema_validates_new_feature_types() -> None:
    """Task 24: Test that new RMM feature types are valid."""
    cfg = {
        "features": [
            {
                "name": "atr_pct",
                "type": "ATRPercentile",
                "params": {"atr_length": 14, "lookback": 20},
            },
            {
                "name": "rvol",
                "type": "RealizedVolatility",
                "params": {"length": 20},
            },
            {"name": "vol_z", "type": "VolumeZScore", "params": {"length": 20}},
        ],
        "regimes": [
            {
                "label": "high_vol",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"ref": "rvol"},
                            "right": 0.02,
                        }
                    ]
                },
            }
        ],
    }
    validate_rmm_config(cfg)


def test_rmm_jsonschema_validates_new_predicate_types() -> None:
    """Task 28: Test that new RMM predicate types are valid."""
    cfg = {
        "features": [
            {
                "name": "atr_pct",
                "type": "ATRPercentile",
                "params": {"atr_length": 14, "lookback": 20},
            },
            {
                "name": "rvol",
                "type": "RealizedVolatility",
                "params": {"length": 20},
            },
        ],
        "regimes": [
            {
                "label": "high_vol",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "percentile_is_above",
                            "left": {"ref": "atr_pct"},
                            "right": 80,
                        }
                    ]
                },
            },
            {
                "label": "moderate_vol",
                "confidence": 0.7,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "volatility_is_between",
                            "left": {"ref": "rvol"},
                            "lower": 0.005,
                            "upper": 0.015,
                        }
                    ]
                },
            },
        ],
    }
    validate_rmm_config(cfg)
