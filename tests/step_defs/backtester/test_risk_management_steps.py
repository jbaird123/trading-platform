from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when
from trading_platform.backtester.core import run_backtest

# Link scenarios from the feature file
scenarios("../../features/backtester/risk_management.feature")


@given(
    parsers.parse(
        "the backtester is configured with a stop-loss of {sl:f} "
        "and a take-profit of {tp:f}"
    )
)
def given_backtester_risk_config(shared_context: dict, sl: float, tp: float):
    """Stores the stop-loss and take-profit configuration."""
    shared_context["stop_loss"] = sl
    shared_context["take_profit"] = tp


@given(parsers.parse("the low price at bar {bar_index:d} is {price:f}"))
def given_low_price_at_bar(shared_context: dict, bar_index: int, price: float):
    """Sets the low price for a specific bar."""
    df = shared_context["market_data"]
    idx = df.index[bar_index - 1]
    df.loc[idx, "low"] = price


@given(parsers.parse("the high price at bar {bar_index:d} is {price:f}"))
def given_high_price_at_bar(shared_context: dict, bar_index: int, price: float):
    """Sets the high price for a specific bar."""
    df = shared_context["market_data"]
    idx = df.index[bar_index - 1]
    df.loc[idx, "high"] = price


@then(parsers.parse('the trade should have an exit reason of "{reason}"'))
def then_trade_exit_reason_is(shared_context: dict, reason: str):
    """Asserts the exit reason of the first generated trade."""
    trades = shared_context["trades"]
    assert len(trades) > 0, "No trades were generated."
    assert trades[0].exit_reason == reason


@when("the backtest is run")
def when_backtest_is_run(shared_context: dict) -> None:
    """Calls the backtester logic and stores the resulting trades."""
    trades = run_backtest(
        market_data=shared_context["market_data"],
        signals=shared_context["signals"],
        stop_loss=shared_context.get("stop_loss"),
        take_profit=shared_context.get("take_profit"),
    )
    shared_context["trades"] = trades
