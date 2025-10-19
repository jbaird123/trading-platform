# Validates: [BT-7.6]
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_with_sl_tp


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


@pytest.mark.req_BT_7_6
def test_tie_break_stop_then_tp_for_long():
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [100.0, 105.0],
            "low": [100.0, 95.0],
            "close": [100.0, 100.0],
            "volume": [1, 1],
        },
        index=idx,
    )
    strategy = _dummy_strategy_with_sl_tp(95.0, 105.0)
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", "exit_long"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        rem_config={
            "stop_loss": {"absolute_price": 95.0},
            "take_profit": {"absolute_price": 105.0},
        },
        instrument=_instrument(),
    )
    rem = RiskExitManager(config=config.rem_config or {})
    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, _, _ = result
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_price == 95.0 and t.exit_reason == "stop-loss"
