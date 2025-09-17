# ruff: noqa: E501
from pytest_bdd import given


@given(
    'the strategy is an EMA Crossover with '
    'fast_period={fast_period} and '
    'slow_period={slow_period}'
)
def an_ema_crossover_strategy(fast_period: str, slow_period: str, shared_context: dict) -> None:
    shared_context["strategy_name"] = "EMA Crossover"
    shared_context["strategy_params"] = {"fast_period": int(fast_period), "slow_period": int(slow_period)}