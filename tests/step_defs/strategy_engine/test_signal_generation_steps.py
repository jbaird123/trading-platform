# ruff: noqa: E501
from __future__ import annotations

from pytest_bdd import given, parsers


@given(
    parsers.parse(
        "the strategy is an EMA Crossover with "
        "fast_period={fast_period} and slow_period={slow_period}"
    )
)
def an_ema_crossover_strategy(
    fast_period: str, slow_period: str, shared_context: dict
) -> None:
    shared_context["strategy_name"] = "EMA Crossover"
    shared_context["strategy_params"] = {
        "fast_period": int(fast_period),
        "slow_period": int(slow_period),
    }
