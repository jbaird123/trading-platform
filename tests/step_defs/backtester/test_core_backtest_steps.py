# Validates: [BT-7.1]
from __future__ import annotations

from pytest_bdd import given, parsers, then


@given(parsers.parse("a signal to go long"), target_fixture="shared_context")
def a_signal_to_go_long(market_data) -> dict:
    """Prepares an enter_long command for the first bar."""
    signals = market_data["signals"].copy()
    signals.iloc[0] = "enter_long"
    return {"market_data": market_data["market_data"], "signals": signals}


@then("a long trade should be recorded")
def a_long_trade_is_recorded(shared_context: dict) -> None:
    """Asserts that one long trade was created."""
    trades = shared_context["trades"]
    assert len(trades) == 1
    assert trades[0].side == "long"
