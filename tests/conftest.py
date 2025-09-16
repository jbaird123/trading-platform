from __future__ import annotations

import logging

import pandas as pd
import pytest
from pytest_bdd import given, parsers, then, when
from trading_platform.backtester.core import run_backtest

from tests.backtester.dummy_objects import (
    _dummy_strategy_cfg,
    _dummy_strategy_with_sl_tp,
)


@pytest.fixture
def shared_context() -> dict:
    """A dictionary to share state between test steps."""
    return {}


@given('a market data series with columns "open", "high", "low", "close", "volume"')
def given_market_data_series(shared_context: dict):
    """Initializes a placeholder DataFrame for market data."""
    # We'll create a DataFrame with enough rows for the test scenarios.
    # The actual values will be set in subsequent step
    num_bars = 5  # A reasonable default for the tests
    logging.info(f"Creating market data series with {num_bars} bars")

    df = pd.DataFrame(
        index=pd.to_datetime([f"2023-01-01 00:{i:02d}:00" for i in range(num_bars)]),
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
    # Use the same index as market_data to avoid IndexError
    shared_context["signals"] = pd.Series(
        "flat", index=shared_context["market_data"].index, dtype=str
    )
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
    shared_context["market_data"].loc[
        shared_context["market_data"].index[bar_index - 1], "close"
    ] = price


@given("the backtest has enough market data")
def given_the_backtest_has_enough_market_data(shared_context: dict):
    """The backtest is run with three bars"""
    # This step is mostly for readability in feature files.
    # The actual data setup is handled by given_market_data_series.
    # We can add a check here if needed, but for now, it's a pass-through.
    assert len(shared_context["market_data"]) >= 3


@when("the backtest is run")
def when_backtest_is_run(shared_context: dict) -> None:
    """Calls the backtester logic and stores the resulting trades."""
    sl = shared_context.get("stop_loss")
    tp = shared_context.get("take_profit")

    # If sl or tp are present, use the specific strategy helper
    if sl is not None or tp is not None:
        strategy = _dummy_strategy_with_sl_tp(float(sl or 0.0), float(tp or 0.0))
    else:
        strategy = _dummy_strategy_cfg()

    trades = run_backtest(
        market_data=shared_context["market_data"],
        signals=shared_context["signals"],
        strategy=strategy,
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
        "the trade should have an entry price of {entry_price:f} "
        "and an exit price of {exit_price:f}"
    )
)
def then_trade_prices_are(
    shared_context: dict, entry_price: float, exit_price: float
) -> None:
    """Asserts the entry and exit prices of the first generated trade."""
    assert len(shared_context["trades"]) > 0, "No trades were generated to check."
    trade = shared_context["trades"][0]
    logging.info("Asserting entry %s == %s", trade.entry_price, entry_price)
    logging.info("Asserting exit %s == %s", trade.exit_price, exit_price)
    assert trade.entry_price == pytest.approx(entry_price)
    assert trade.exit_price == pytest.approx(exit_price)
