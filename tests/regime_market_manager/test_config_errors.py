from __future__ import annotations

import pytest
from trading_platform.regime_market_manager.config import validate_rmm_config


def test_rmm_missing_regimes_raises():
    with pytest.raises(ValueError):
        validate_rmm_config({})


def test_rmm_label_must_be_string():
    cfg = {"regimes": [{"label": 123, "confidence": 0.5, "conditions": {"all_of": []}}]}
    with pytest.raises(ValueError):
        validate_rmm_config(cfg)


def test_rmm_confidence_out_of_range():
    cfg = {"regimes": [{"label": "x", "confidence": 2.0, "conditions": {"any_of": []}}]}
    with pytest.raises(ValueError):
        validate_rmm_config(cfg)


def test_rmm_conditions_object_required():
    cfg = {"regimes": [{"label": "x", "confidence": 0.1, "conditions": []}]}
    with pytest.raises(ValueError):
        validate_rmm_config(cfg)


def test_rmm_predicates_non_empty():
    cfg = {"regimes": [{"label": "x", "confidence": 0.1, "conditions": {"all_of": []}}]}
    with pytest.raises(ValueError):
        validate_rmm_config(cfg)
