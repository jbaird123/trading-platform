# Validates: [BT-7.10]
from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pandas as pd
import pytest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg
from tests.test_helpers import (
    get_empty_global_features_path,
    run_backtest_simulation,
)


def _dummy_strategy():
    strat = _dummy_strategy_cfg()
    return strat


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


@pytest.mark.req_BT_7_10
def test_return_skips_without_exposure():
    idx = [datetime(2024, 1, 1, h) for h in range(1)]
    df = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}, index=idx
    )
    strategy = _dummy_strategy()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)
    result = run_backtest_simulation(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=False,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    trades, _, skipped = cast(
        tuple[list[Any], list[tuple[datetime, float]], list[dict[str, Any]]], result
    )
    assert isinstance(skipped, list)
