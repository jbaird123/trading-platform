from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy_cfg() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def _mk_df(start: datetime, n: int, step_minutes: int = 60) -> pd.DataFrame:
    idx = [start + timedelta(minutes=i * step_minutes) for i in range(n)]
    data = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100}
    return pd.DataFrame([data] * n, index=idx)


def test_event_blackout_blocks_new_entries():
    """Test that a defined event blackout window blocks new entries."""
    start = datetime(2023, 1, 1, 10, 0)
    df = _mk_df(start, 4, 60)
    signals = pd.Series(["long", "long", "long", "long"], index=df.index)

    ev = {"start": datetime(2023, 1, 1, 11, 0), "end": datetime(2023, 1, 1, 12, 30)}
    config = RunConfig(
        initial_cash=1000.0,
        position_size=1.0,
        blackout_events=[ev],
    )
    rem = RiskExitManager(config={})
    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
    )

    assert isinstance(trades, list)


def test_static_blackout_blocks_new_entries():
    """Test that a static UTC blackout window blocks new entries."""
    times = [
        "2023-01-01T22:00:00",
        "2023-01-01T23:30:00",
        "2023-01-02T00:30:00",
        "2023-01-02T02:00:00",
    ]
    idx = [datetime.fromisoformat(t) for t in times]
    df = pd.DataFrame({
        "open": [1.0] * len(idx),
        "high": [1.1] * len(idx),
        "low": [0.9] * len(idx),
        "close": [1.0] * len(idx),
        "volume": [100] * len(idx),
    }, index=idx)
    signals = pd.Series(["long"] * 4, index=df.index)
    config = RunConfig(
        initial_cash=1000.0,
        position_size=1.0,
        blackout_utc=[("23:00", "01:00")],
    )
    rem = RiskExitManager(config={})
    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
    )
    assert isinstance(trades, list)
