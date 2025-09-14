from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from trading_platform.regime_market_manager.classification import classify_regime
from trading_platform.regime_market_manager.config import RegimeManagerConfig


@pytest.fixture
def shared_context() -> dict:
    """A dictionary to share state between test steps."""
    return {}


# Link scenarios from the feature file
scenarios("../../features/regime_market_manager/market_regime_classification.feature")


# --- Given Steps ---


@given("a market data series with pre-calculated indicator values")
def given_market_data_with_indicators(shared_context: dict):
    """Initializes a dictionary to hold indicator values for the test."""
    shared_context["indicators"] = {}


@given(parsers.parse('the indicator "{indicator_name}" has a value of {value:f}'))
def given_indicator_has_value(shared_context: dict, indicator_name: str, value: float):
    """Stores a specific indicator value in the shared context."""
    shared_context["indicators"][indicator_name] = value


# --- When Steps ---


@when("the market regime is classified")
def when_market_regime_is_classified(shared_context: dict):
    """Calls the RMM logic to classify the regime and stores the result."""
    config = RegimeManagerConfig()  # Use default config for these tests
    result = classify_regime(shared_context["indicators"], config)
    shared_context["regime_result"] = result


# --- Then Steps ---


@then(parsers.parse('the regime should be "{expected_regime}"'))
def then_regime_should_be(shared_context: dict, expected_regime: str):
    """Asserts that the classified regime is correct."""
    actual_regime = shared_context["regime_result"]["regime"]
    assert actual_regime == expected_regime


@then(parsers.parse('the confidence should be "{expected_confidence}"'))
def then_confidence_should_be(shared_context: dict, expected_confidence: str):
    """Asserts that the classification confidence is correct."""
    actual_confidence = shared_context["regime_result"]["confidence"]
    assert actual_confidence == expected_confidence
