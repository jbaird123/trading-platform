from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import validate_strategy_config


def test_strategy_jsonschema_validates_required_fields():
    valid = {
        "strategy_name": "X",
        "entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
        ],
        "exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1}]}
        ],
    }
    validate_strategy_config(valid)


def test_strategy_jsonschema_reports_missing_name():
    invalid = {
        "entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
        ],
        "exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1}]}
        ],
    }
    with pytest.raises(ValueError) as e:
        validate_strategy_config(invalid)
    assert "strategy" in str(e.value)
