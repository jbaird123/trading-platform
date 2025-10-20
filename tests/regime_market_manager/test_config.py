"""Consolidated tests for RMM configuration validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from trading_platform.regime_market_manager.config import (
    RegimeManagerConfig,
    validate_rmm_config,
)

CONFIG_MODULE = "trading_platform.regime_market_manager.config"


# --- Basic validation behaviour -------------------------------------------------


def test_validate_rmm_config_requires_regimes() -> None:
    with pytest.raises(ValueError, match="rmm config must be an object"):
        validate_rmm_config("invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="rmm config must be an object"):
        validate_rmm_config(None)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        validate_rmm_config({})


def test_validate_rmm_config_accepts_any_of_minimal_valid() -> None:
    config = {
        "regimes": [
            {
                "label": "range",
                "confidence": 0.5,
                "conditions": {
                    "any_of": [{"condition": "is_below", "left": {"value": 10}, "right": {"value": 20}}]
                },
            }
        ]
    }
    validate_rmm_config(config)


# --- Coverage of detailed error branches ----------------------------------------


def test_validate_rmm_config_without_jsonschema() -> None:
    """Test that RMM validation works without jsonschema (it's no longer required)."""
    # Empty regimes should still raise error (basic validation)
    invalid_config: dict[str, list[str]] = {"regimes": []}
    with pytest.raises(ValueError, match="regimes must be a non-empty array"):
        validate_rmm_config(invalid_config)


def test_validate_rmm_config_regimes_must_be_non_empty_list() -> None:
    """Test that regimes must be a non-empty list."""
    payload: Any
    for payload in ("invalid", []):
        with pytest.raises(ValueError, match="regimes must be a non-empty array"):
            validate_rmm_config({"regimes": payload})


def test_validate_rmm_config_regime_structure() -> None:
    """Test that regime structure is validated correctly."""
    with pytest.raises(ValueError, match="regime must be an object"):
        validate_rmm_config({"regimes": ["bad"]})

    with pytest.raises(ValueError, match="regime.label must be a string"):
        validate_rmm_config({"regimes": [{"label": 123}]})

    with pytest.raises(ValueError, match="regime.confidence must be 0..1"):
        validate_rmm_config({"regimes": [{"label": "x", "confidence": "bad"}]})

    with pytest.raises(ValueError, match="regime.confidence must be 0..1"):
        validate_rmm_config({"regimes": [{"label": "x", "confidence": 1.5}]})

    bad_conditions = {
        "regimes": [{"label": "x", "conditions": "bad", "confidence": 0.5}]
    }
    with pytest.raises(ValueError, match="regime.conditions must be an object"):
        validate_rmm_config(bad_conditions)

    missing_clauses = {
        "regimes": [
            {
                "label": "x",
                "confidence": 0.5,
                "conditions": {},
            }
        ]
    }
    with pytest.raises(
        ValueError, match="regime.conditions requires all_of or any_of"
    ):
        validate_rmm_config(missing_clauses)

    empty_predicates = {
        "regimes": [
            {
                "label": "x",
                "confidence": 0.5,
                "conditions": {"all_of": []},
            }
        ]
    }
    with pytest.raises(
        ValueError, match="predicate list must be a non-empty array"
    ):
        validate_rmm_config(empty_predicates)

    non_list_predicates = {
        "regimes": [
            {
                "label": "x",
                "confidence": 0.5,
                "conditions": {"any_of": "bad"},
            }
        ]
    }
    with pytest.raises(
        ValueError, match="predicate list must be a non-empty array"
    ):
        validate_rmm_config(non_list_predicates)


# --- Smoke coverage for dataclass wrapper ---------------------------------------


def test_regime_manager_config_defaults() -> None:
    cfg = RegimeManagerConfig()
    assert cfg.trend_indicator
    assert cfg.trend_threshold_high > cfg.trend_threshold_low
    assert cfg.slope_threshold > 0
