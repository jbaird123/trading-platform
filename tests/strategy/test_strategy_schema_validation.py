# Validates: [SE-3.9]
from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import validate_strategy_config

MINIMAL_LONG_RULES = {
    "long_entry_rules": [
        {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
    ],
    "long_exit_rules": [
        {"any_of": [{"condition": "is_below", "left": "close", "right": 1}]}
    ],
}

MINIMAL_SHORT_RULES = {
    "short_entry_rules": [
        {"any_of": [{"condition": "is_below", "left": "close", "right": 1}]}
    ],
    "short_exit_rules": [
        {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
    ],
}


def test_strategy_validation_accepts_valid_long_only():
    cfg = {"strategy_name": "LongOnly", **MINIMAL_LONG_RULES}
    validate_strategy_config(cfg)  # does not raise


def test_strategy_validation_accepts_valid_short_only():
    cfg = {"strategy_name": "ShortOnly", **MINIMAL_SHORT_RULES}
    validate_strategy_config(cfg)  # does not raise


def test_strategy_validation_accepts_valid_long_and_short():
    cfg = {"strategy_name": "LongAndShort", **MINIMAL_LONG_RULES, **MINIMAL_SHORT_RULES}
    validate_strategy_config(cfg)  # does not raise


def test_strategy_validation_rejects_missing_strategy_name():
    cfg = {**MINIMAL_LONG_RULES}
    with pytest.raises(ValueError, match="Strategy schema validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_accepts_entry_rules_without_exit():
    """Exit rules are optional - strategies can rely solely on trailing stops."""
    cfg = {
        "strategy_name": "EntryOnly",
        "long_entry_rules": MINIMAL_LONG_RULES["long_entry_rules"],
    }
    # Should not raise - exit rules are optional
    validate_strategy_config(cfg)


def test_strategy_validation_rejects_incomplete_short_pair():
    cfg = {
        "strategy_name": "Incomplete",
        "short_exit_rules": MINIMAL_SHORT_RULES["short_exit_rules"],
    }
    with pytest.raises(ValueError, match="Strategy schema validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_bad_predicate_condition():
    cfg = {
        "strategy_name": "S",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_sideways", "left": "close", "right": 1}]}
        ],
        "long_exit_rules": MINIMAL_LONG_RULES["long_exit_rules"],
    }
    with pytest.raises(ValueError, match="Strategy schema validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_empty_predicate_list():
    cfg = {
        "strategy_name": "S",
        "long_entry_rules": [{"any_of": []}],
        "long_exit_rules": MINIMAL_LONG_RULES["long_exit_rules"],
    }
    with pytest.raises(ValueError, match="Strategy schema validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_missing_allof_anyof():
    cfg = {
        "strategy_name": "S",
        "long_entry_rules": [{}],
        "long_exit_rules": MINIMAL_LONG_RULES["long_exit_rules"],
    }
    with pytest.raises(ValueError, match="Strategy schema validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_jsonschema_type_error():
    # This config violates the schema because strategy_name must be a string.
    cfg = {"strategy_name": 123, **MINIMAL_LONG_RULES}
    with pytest.raises(ValueError, match="Strategy schema validation error"):
        validate_strategy_config(cfg)
