# Validates: [SE-3.9]
from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import validate_strategy_config


def test_strategy_pydantic_validates_required_fields():
    """Test that Pydantic validates required fields."""
    valid = {
        "strategy_name": "X",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 1}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 1}}]}
        ],
    }
    validate_strategy_config(valid)


def test_strategy_pydantic_reports_missing_name():
    """Test that Pydantic reports missing required field strategy_name."""
    invalid = {
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 1}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 1}}]}
        ],
    }
    with pytest.raises(ValueError, match="Strategy validation error"):
        validate_strategy_config(invalid)
