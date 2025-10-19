# Validates: [BT-7.16]
from __future__ import annotations

from pytest_bdd import given, parsers, then, when
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_with_sl_tp


@given(
    parsers.parse(
        "the backtester is configured with a stop-loss of {sl} and a "
        "take-profit of {tp}"
    )
)
def backtester_is_configured_with_risk(sl: str, tp: str, shared_context: dict) -> None:
    shared_context["stop_loss"] = float(sl)
    shared_context["take_profit"] = float(tp)


@when("the backtest is run")
def when_backtest_is_run(shared_context: dict) -> None:
    """Calls the backtester logic and stores the resulting trades."""
    sl = shared_context.get("stop_loss")
    tp = shared_context.get("take_profit")
    strategy = _dummy_strategy_with_sl_tp(float(sl or 0.0), float(tp or 0.0))
    strategy.generate_signals(
        shared_context["market_data"]
    )  # Populate _feature_df for context lookups
    config = RunConfig(
        user_id="test_user",
        run_seed=123,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=True,
        rem_config={
            "stop_loss": {"price_offset": sl},
            "take_profit": {"price_offset": tp},
        },
        instrument={"symbol": "EURUSD"},
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=config.rem_config or {})
    trades = run_backtest(
        market_data=shared_context["market_data"],
        signals=shared_context["signals"],
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=False,
        return_skips=False,
    )
    shared_context["trades"] = trades


@then(parsers.parse("the trade should be closed by a {reason}"))
def trade_is_closed_by_reason(reason: str, shared_context: dict) -> None:
    trades = shared_context["trades"]
    assert len(trades) == 1
    assert trades[0].exit_reason == reason
