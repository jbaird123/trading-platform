from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from trading_platform.backtester.core import (
    _simulate_counterfactual_exact,
    run_backtest,
)
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg

# Minimal instrument for testing
TEST_INSTRUMENT = {
    "symbol": "EURUSD",
    "asset_class": "Forex",
    "point_value": 1.0,
    "tick_size": 0.00001,
    "pip_location": 0.0001,
}


def test_run_backtest_returns_trades_and_exposure_only() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    df = pd.DataFrame(
        {
            "open": [1.0, 1.01, 1.02, 1.03],
            "high": [1.01, 1.02, 1.03, 1.04],
            "low": [0.99, 1.0, 1.01, 1.02],
            "close": [1.0, 1.02, 1.01, 1.03],
            "volume": [100] * 4,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    signals = pd.Series(["enter_long", "exit_long", None, None], index=idx)
    config = RunConfig(
        user_id="tester",
        run_seed=7,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument={"symbol": "EURUSD"},
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    result = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
    )
    trades, exposure = result[:2]  # Extract only trades and exposure

    assert isinstance(trades, list)
    assert isinstance(exposure, list)
    assert len(exposure) == len(df)
    assert all(isinstance(ts, datetime) for ts, _ in exposure)


class _NeverExitREM:
    def check_exits(
        self,
        position: Any,
        current_bar: pd.Series,
        signal: Any = None,
        data_handler: Any = None,
        prior_bar: pd.Series | None = None,
    ) -> None:
        return None


def test_counterfactual_exact_exit_kind_end() -> None:
    idx = pd.date_range("2024-02-01", periods=4, freq="h")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [100] * 4,
        },
        index=idx,
    )
    entry_index = 1
    entry_price = float(df.iloc[entry_index]["close"])

    result = _simulate_counterfactual_exact(
        market_data=df,
        strategy=_dummy_strategy_cfg(),
        start_index=entry_index,
        side="short",
        entry_price=entry_price,
        size=1.0,
        instrument=TEST_INSTRUMENT,
        cost_model={},
        rem=_NeverExitREM(),  # type: ignore[arg-type]
        symbol="EURUSD",
    )

    assert result["cf_mode"] == "exact"
    assert result["cf_exit_kind"] == "end"
    assert result["cf_exit_price"] == float(df.iloc[-1]["close"])
