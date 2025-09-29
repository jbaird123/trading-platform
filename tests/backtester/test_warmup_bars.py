# Validates: [BT-7.7]
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg


def _mk_df(n: int) -> pd.DataFrame:
    start = datetime(2023, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(n)]
    data = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100}
    return pd.DataFrame([data] * n, index=idx)


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


@pytest.mark.req_BT_7_7
def test_warmup_delays_first_entry_until_threshold():
    # 5 bars hourly, warmup of 3 bars → first entry allowed at index 3 (4th bar)
    df = _mk_df(5)
    # Signals: long on first 4 bars, flat on last bar to force close
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["long", "long", "long", "long", "flat"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        warmup_bars=3,
        instrument=_instrument(),
    )
    rem = RiskExitManager(config={})
    result = run_backtest(

        market_data=df,

        signals=sig,

        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, _, _ = result  # type: ignore[misc]
    # One completed trade: entry at 4th bar, exit on 5th due to flat
    assert len(trades) == 1  # type: ignore[arg-type]
    assert trades[0].entry_time == df.index[3]  # type: ignore[index]


@pytest.mark.req_BT_7_7
def test_no_warmup_allows_immediate_entry():
    df = _mk_df(3)
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["long", "flat", "flat"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        warmup_bars=0,
        instrument=_instrument(),
    )
    rem = RiskExitManager(config={})
    result = run_backtest(

        market_data=df,

        signals=sig,

        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, _, _ = result  # type: ignore[misc]
    # First trade should enter at the first bar
    assert len(trades) == 1  # type: ignore[arg-type]
    assert trades[0].entry_time == df.index[0]  # type: ignore[index]
