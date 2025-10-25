# Validates: [SE-3.9]
from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import validate_strategy_config

MINIMAL_LONG_RULES = {
    "long_entry_rules": [
        {
            "any_of": [
                {
                    "condition": "is_above",
                    "left": {"field": "close"},
                    "right": {"value": 1},
                }
            ]
        }
    ],
    "long_exit_rules": [
        {
            "any_of": [
                {
                    "condition": "is_below",
                    "left": {"field": "close"},
                    "right": {"value": 1},
                }
            ]
        }
    ],
}

MINIMAL_SHORT_RULES = {
    "short_entry_rules": [
        {
            "any_of": [
                {
                    "condition": "is_below",
                    "left": {"field": "close"},
                    "right": {"value": 1},
                }
            ]
        }
    ],
    "short_exit_rules": [
        {
            "any_of": [
                {
                    "condition": "is_above",
                    "left": {"field": "close"},
                    "right": {"value": 1},
                }
            ]
        }
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
    with pytest.raises(ValueError, match="Strategy validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_accepts_entry_rules_without_exit():
    """Exit rules are optional - strategies can rely solely on trailing stops."""
    cfg = {
        "strategy_name": "EntryOnly",
        "long_entry_rules": MINIMAL_LONG_RULES["long_entry_rules"],
    }
    # Should not raise - exit rules are optional
    validate_strategy_config(cfg)


def test_strategy_validation_rejects_exit_rules_without_entry():
    """
    STRICT VALIDATION: Rejects strategies with only exit rules (no entry
    rules).

    A strategy without entry rules cannot generate trades, so this is a
    configuration error. Fail loudly to catch this mistake early.
    """
    cfg = {
        "strategy_name": "ExitOnly",
        "short_exit_rules": MINIMAL_SHORT_RULES["short_exit_rules"],
    }
    # Should raise - strategies need at least one entry rule
    with pytest.raises(ValueError, match="must have at least one entry rule"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_invalid_condition_string():
    """STRICT VALIDATION: Rejects invalid condition strings (using enum).

    Conditions must be from the StrategyCondition enum.
    Typos and invalid conditions are caught at config load time, not runtime.
    """
    cfg = {
        "strategy_name": "S",
        "long_entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_sideways",
                        "left": {"field": "close"},
                        "right": {"value": 1},
                    }
                ]
            }
        ],
        "long_exit_rules": MINIMAL_LONG_RULES["long_exit_rules"],
    }
    # Should raise - "is_sideways" is not a valid condition
    with pytest.raises(ValueError, match="Strategy validation error"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_empty_predicate_list():
    """STRICT VALIDATION: Rejects empty predicate lists (min_length=1).

    Empty predicate lists cannot generate signals, so this is a configuration error.
    Fail loudly to catch this mistake early.
    """
    cfg = {
        "strategy_name": "S",
        "long_entry_rules": [{"any_of": []}],
        "long_exit_rules": MINIMAL_LONG_RULES["long_exit_rules"],
    }
    # Should raise - predicate lists must have at least one item
    with pytest.raises(ValueError, match="at least 1 item"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_empty_rule_blocks():
    """STRICT VALIDATION: Rejects rule blocks without all_of or any_of.

    Rule blocks must have exactly one of: all_of or any_of.
    Empty rule blocks cannot generate signals, so this is a configuration error.
    """
    cfg = {
        "strategy_name": "S",
        "long_entry_rules": [{}],
        "long_exit_rules": MINIMAL_LONG_RULES["long_exit_rules"],
    }
    # Should raise - rule blocks need all_of or any_of
    with pytest.raises(ValueError, match="exactly one of"):
        validate_strategy_config(cfg)


def test_strategy_validation_rejects_pydantic_type_error():
    # This config violates the Pydantic model because strategy_name must be a string.
    cfg = {"strategy_name": 123, **MINIMAL_LONG_RULES}
    with pytest.raises(ValueError, match="Strategy validation error"):
        validate_strategy_config(cfg)
