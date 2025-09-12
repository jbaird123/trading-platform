from __future__ import annotations

import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from trading_platform.strategy.exponential_moving_average import (
    generate_ema_crossover_signals,
)


@pytest.fixture
def shared_context() -> dict:
    """A dictionary to share state between test steps."""
    # Using a dictionary for shared_context is a common pattern in pytest-bdd
    # to pass data between `Given`, `When`, and `Then` steps.
    return {}


# This single line links all scenarios in the specified feature file
# to this step definition file.
scenarios("../../features/strategy_engine/signal_generation.feature")


# --- Given Steps ---


@given('a market data series with columns "open", "high", "low", "close", "volume"')
def given_market_data_series(shared_context: dict):
    """Initializes a placeholder for market data in the shared context."""
    # We will create a more detailed DataFrame in subsequent steps.
    shared_context["market_data"] = pd.DataFrame()


@given(
    parsers.parse(
        "the strategy is an EMA Crossover with "
        "fast_period={fast_period:d} and slow_period={slow_period:d}"
    )
)
def given_ema_crossover_strategy(
    shared_context: dict, fast_period: int, slow_period: int
):
    """Stores the strategy parameters in the shared context."""
    shared_context["strategy_params"] = {
        "fast_period": fast_period,
        "slow_period": slow_period,
    }


@given("the market data is prepared for the strategy")
def given_market_data_is_prepared(shared_context: dict):
    """Prepares the market data with mock indicator values for the test."""
    # We'll create a simple two-row DataFrame to represent "previous"
    # and "current" bars.
    shared_context["market_data"] = pd.DataFrame(
        {
            "ema_fast": [0.0, 0.0],  # [previous, current]
            "ema_slow": [0.0, 0.0],  # [previous, current]
        }
    )


@given(parsers.parse('the "{indicator}" at the previous bar is {value:f}'))
def given_indicator_at_previous_bar(shared_context: dict, indicator: str, value: float):
    """Sets the value for a given indicator on the 'previous' bar (index 0)."""
    shared_context["market_data"].loc[0, indicator] = value


@given(parsers.parse('the "{indicator}" at the current bar is {value:f}'))
def given_indicator_at_current_bar(shared_context: dict, indicator: str, value: float):
    """Sets the value for a given indicator on the 'current' bar (index 1)."""
    shared_context["market_data"].loc[1, indicator] = value


# --- When Steps ---


@when("the strategy generates signals")
def when_strategy_generates_signals(shared_context: dict):
    """Calls the strategy logic to generate signals and stores them in the context."""
    params = shared_context["strategy_params"]
    signals = generate_ema_crossover_signals(
        data=shared_context["market_data"],
        fast_period=params["fast_period"],
        slow_period=params["slow_period"],
    )
    shared_context["signals"] = signals


# --- Then Steps ---


@then(parsers.parse('the signal for the current bar should be "{expected_signal}"'))
def then_signal_is(shared_context: dict, expected_signal: str):
    """Asserts that the generated signal for the current bar is correct."""
    # The "current" bar is the last one in our test's DataFrame (index 1)
    actual_signal = shared_context["signals"].iloc[-1]
    assert actual_signal == expected_signal
