from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


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
    """(Skeleton) This step will eventually call the RMM logic."""
    pytest.fail("Step not implemented: when_market_regime_is_classified")


# --- Then Steps ---


@then(parsers.parse('the regime should be "{expected_regime}"'))
def then_regime_should_be(shared_context: dict, expected_regime: str):
    """(Skeleton) This step will assert the classified regime is correct."""
    pytest.fail("Step not implemented: then_regime_should_be")


@then(parsers.parse('the confidence should be "{expected_confidence}"'))
def then_confidence_should_be(shared_context: dict, expected_confidence: str):
    """(Skeleton) This step will assert the classification confidence is correct."""
    pytest.fail("Step not implemented: then_confidence_should_be")
