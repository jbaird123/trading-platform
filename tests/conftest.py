# Validates: [SYS-1.10.3]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from pytest_bdd import given, parsers, when

from tests.backtester.dummy_objects import (
    _dummy_strategy_cfg,
    _dummy_strategy_with_sl_tp,
)


@given(parsers.parse('a market data series with columns "{columns}"'))
def market_data(columns: str) -> dict:
    """Creates a DataFrame with a datetime index."""
    start = datetime(2023, 1, 1)
    end = datetime(2023, 1, 2)
    freq = pd.to_timedelta("1h")
    idx = pd.date_range(start, end, freq=freq)
    df = pd.DataFrame(index=idx)
    for col in columns.split(", "):
        df[col] = 100.0
    signals = pd.Series("flat", index=idx)
    return {"market_data": df, "signals": signals}


@when("the backtest is run")
def when_backtest_is_run(shared_context: dict) -> None:
    """Calls the backtester logic and stores the resulting trades."""
    from trading_platform.backtester.core import run_backtest
    from trading_platform.core.config import RunConfig
    from trading_platform.risk_manager.core import RiskExitManager

    sl = shared_context.get("stop_loss")
    tp = shared_context.get("take_profit")

    # If sl or tp are present, use the specific strategy helper
    if sl is not None or tp is not None:
        strategy = _dummy_strategy_with_sl_tp(float(sl or 0.0), float(tp or 0.0))
        rem_config = {
            "stop_loss": {"value": sl, "type": "price"},
            "take_profit": {"value": tp, "type": "price"},
        }
    else:
        strategy = _dummy_strategy_cfg()
        rem_config = {}

    config = RunConfig(
        user_id="test_user",
        run_seed=123,
        log_level="INFO",
        initial_cash=10000.0,
        allow_flip_on_bar=True,
        rem_config=rem_config
    )
    rem = RiskExitManager(config=config.rem_config or {})
    trades = run_backtest(
        market_data=shared_context["market_data"],
        signals=shared_context["signals"],
        strategy=strategy,
        config=config,
        rem=rem,
    )
    shared_context["trades"] = trades
