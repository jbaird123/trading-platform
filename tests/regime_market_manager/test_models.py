"""Tests for the RMM Pydantic models."""

import pytest
from pydantic import ValidationError

from trading_platform.regime_market_manager.models import RMMConfig


@pytest.fixture
def valid_rmm_config_dict() -> dict:
    """Provides a valid, comprehensive RMM configuration dictionary."""
    return {
        "name": "Test RMM",
        "version": "1.0",
        "timeframe": "1D",
        "features": [
            {
                "name": "ADX_14",
                "type": "ADX",
                "params": {"length": 14},
            }
        ],
        "policy": {
            "min_confidence": 0.5,
            "allow_labels": ["trend_up"],
        },
        "regimes": [
            {
                "label": "trend_up",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"ref": "ADX_14"},
                            "right": 25.0,
                        }
                    ]
                },
            },
            {
                "label": "range",
                "confidence": 0.6,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_below",
                            "left": {"ref": "ADX_14"},
                            "right": 20.0,
                        }
                    ]
                },
            },
        ],
    }


def test_valid_rmm_config_parses_correctly(valid_rmm_config_dict: dict):
    """Test that a valid RMM configuration is parsed without errors."""
    try:
        rmm_config = RMMConfig(**valid_rmm_config_dict)
        assert rmm_config.name == "Test RMM"
        assert rmm_config.policy is not None
        assert rmm_config.policy.min_confidence == 0.5
        assert len(rmm_config.regimes) == 2
        assert rmm_config.regimes[0].label == "trend_up"
    except ValidationError as e:
        pytest.fail(f"Valid RMM config failed to parse: {e}")


def test_rejects_unknown_top_level_field(valid_rmm_config_dict: dict):
    """Test that an unknown top-level field raises a ValidationError."""
    invalid_config = valid_rmm_config_dict.copy()
    invalid_config["unknown_field"] = "some_value"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RMMConfig(**invalid_config)


def test_rejects_unknown_nested_field_in_policy(valid_rmm_config_dict: dict):
    """Test that an unknown field in a nested object (policy) fails."""
    invalid_config = valid_rmm_config_dict.copy()
    invalid_config["policy"]["bad_policy_field"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RMMConfig(**invalid_config)


def test_rejects_unknown_nested_field_in_regime(valid_rmm_config_dict: dict):
    """Test that an unknown field in a regime definition fails."""
    invalid_config = valid_rmm_config_dict.copy()
    invalid_config["regimes"][0]["invalid_key"] = "foo"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RMMConfig(**invalid_config)


def test_rejects_invalid_predicate_condition(valid_rmm_config_dict: dict):
    """Test that using an invalid string for a predicate condition fails."""
    invalid_config = valid_rmm_config_dict.copy()
    invalid_config["regimes"][0]["conditions"]["all_of"][0][
        "condition"
    ] = "is_greater_than"  # Invalid condition

    with pytest.raises(ValidationError) as excinfo:
        RMMConfig(**invalid_config)
    assert "Input should be" in str(excinfo.value)


def test_rejects_invalid_feature_type(valid_rmm_config_dict: dict):
    """Test that using an invalid string for a feature type fails."""
    invalid_config = valid_rmm_config_dict.copy()
    invalid_config["features"][0]["type"] = "NonExistentIndicator"

    with pytest.raises(ValidationError) as excinfo:
        RMMConfig(**invalid_config)
    assert "Input should be" in str(excinfo.value)


def test_missing_required_regimes_field(valid_rmm_config_dict: dict):
    """Test that the config is invalid if the required 'regimes' field is missing."""
    invalid_config = valid_rmm_config_dict.copy()
    del invalid_config["regimes"]

    with pytest.raises(ValidationError, match="Field required"):
        RMMConfig(**invalid_config)


def test_empty_regimes_list_is_invalid(valid_rmm_config_dict: dict):
    """Test that the 'regimes' list must contain at least one item."""
    invalid_config = valid_rmm_config_dict.copy()
    invalid_config["regimes"] = []

    with pytest.raises(ValidationError, match="List should have at least 1 item"):
        RMMConfig(**invalid_config)
