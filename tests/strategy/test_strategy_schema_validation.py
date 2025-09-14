from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import validate_strategy_config


def test_strategy_validation_accepts_minimal_valid():
    cfg = {
        "strategy_name": "S",
        "entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
        ],
        "exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1}]}
        ],
    }
    validate_strategy_config(cfg)  # does not raise


def test_strategy_validation_rejects_missing_required():
    cfg = {"entry_rules": [], "exit_rules": []}
    with pytest.raises(ValueError) as e:
        validate_strategy_config(cfg)
    assert "missing required field" in str(e.value)


def test_strategy_validation_rejects_bad_predicate():
    cfg = {
        "strategy_name": "S",
        "entry_rules": [
            {"any_of": [{"condition": "bad", "left": "close", "right": 1}]}
        ],
        "exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1}]}
        ],
    }
    with pytest.raises(ValueError) as e:
        validate_strategy_config(cfg)
    assert "unsupported condition" in str(e.value)
