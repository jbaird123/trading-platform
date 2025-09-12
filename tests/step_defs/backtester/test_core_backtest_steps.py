from __future__ import annotations

import logging

import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from trading_platform.backtester.core import run_backtest


@pytest.fixture
def shared_context() -> dict:
    """A dictionary to share state between test steps."""
    return {}


# Link scenarios from the feature file
scenarios("../../features/backtester/core_backtest.feature")


# --- Given Steps ---


@given('a market data series with columns "open", "high", "low", "close", "volume"')
def given_market_data_series(shared_context: dict):
    """Initializes a placeholder DataFrame for market data."""
    # We'll create a DataFrame with enough rows for the test scenarios.
    # The actual values will be set in subsequent step
    num_bars = 5  # A reasonable default for the tests
    logging.info(f"Creating market data series with {num_bars} bars")

    df = pd.DataFrame(
        index=range(num_bars),
        columns=["open", "high", "low", "close", "volume"],
        dtype=float,
    )
    # Ensure no NaNs in operative columns; default to 0.0 for tests.
    df.loc[:, :] = 0.0
    shared_context["market_data"] = df


@given('a signal series with "long", "short", and "flat" signals')
def given_signal_series(shared_context: dict):
    """Initializes a placeholder Series for signals, aligned with market data."""
    num_bars = len(shared_context["market_data"])
    shared_context["signals"] = pd.Series("flat", index=range(num_bars), dtype=str)
    logging.info(f"Creating signal series with {num_bars} bars")


@given(parsers.parse('the signal at bar {bar_index:d} is "{signal_value}"'))
def given_signal_at_bar(shared_context: dict, bar_index: int, signal_value: str):
    """Sets the signal value for a specific bar."""
    # Gherkin is 1-indexed for readability, pandas is 0-indexed.
    logging.info(f"Setting signal at bar {bar_index} to {signal_value}")
    shared_context["signals"].iloc[bar_index - 1] = signal_value


@given(parsers.parse("the close price at bar {bar_index:d} is {price:f}"))
def given_close_price_at_bar(shared_context: dict, bar_index: int, price: float):
    """Sets the close price for a specific bar."""
    shared_context["market_data"].loc[bar_index - 1, "close"] = price


@given("the backtest has enough market data")
def given_the_backtest_has_enough_market_data(shared_context: dict):
    """The backtest is run with three bars"""
    assert len(shared_context["market_data"]) >= 3


# --- When and Then steps (Skeletons) ---


@when("the backtest is run")
def when_backtest_is_run(shared_context: dict) -> None:
    """Calls the backtester logic and stores the resulting trades."""
    trades = run_backtest(
        market_data=shared_context["market_data"], signals=shared_context["signals"]
    )
    shared_context["trades"] = trades
    logging.info(f"Backtest generated {len(trades)} trades")


@then(parsers.parse("there should be {count:d} trade generated"))
def then_trade_count_is(shared_context: dict, count: int) -> None:
    """Asserts that the correct number of trades were generated."""
    trades = shared_context["trades"]
    logging.info(f"Asserting that {len(trades)} == {count}")
    assert len(shared_context["trades"]) == count


@then(
    parsers.parse(
        "the trade should have an entry price of {entry_price:f} and an exit price of"
        " {exit_price:f}"
    )
)
def then_trade_prices_are(
    shared_context: dict, entry_price: float, exit_price: float
) -> None:
    """Asserts the entry and exit prices of the first generated trade."""
    # This assumes a single trade for the scenario
    assert len(shared_context["trades"]) > 0, "No trades were generated to check."
    trade = shared_context["trades"][0]
    logging.info(f"Asserting trade entry price: {trade.entry_price} == {entry_price}")
    logging.info(f"Asserting trade exit price: {trade.exit_price} == {exit_price}")
    assert trade.entry_price == pytest.approx(entry_price)
    assert trade.exit_price == pytest.approx(exit_price)
