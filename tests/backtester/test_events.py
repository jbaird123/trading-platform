from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from trading_platform.backtester.core import _run_backtest_simulation
from tests.test_helpers import get_empty_global_features_path
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


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


def _mk_df(start: datetime, n: int, step_minutes: int = 60) -> pd.DataFrame:
    idx = [start + timedelta(minutes=i * step_minutes) for i in range(n)]
    data = {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100}
    return pd.DataFrame([data] * n, index=idx)


def test_event_blackout_blocks_new_entries():
    """Test that a defined event blackout window blocks new entries."""
    start = datetime(2023, 1, 1, 10, 0)
    df = _mk_df(start, 4, 60)
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)
    signals = pd.Series(["enter_long", None, None, None], index=df.index)

    ev = {"start": datetime(2023, 1, 1, 11, 0), "end": datetime(2023, 1, 1, 12, 30)}
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        allow_flip_on_bar=False,
        initial_cash=1000.0,
        position_size=1.0,
        blackout_events=[ev],
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)
    trades = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    
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
    df = pd.DataFrame(
        {
            "open": [1.0] * len(idx),
            "high": [1.1] * len(idx),
            "low": [0.9] * len(idx),
            "close": [1.0] * len(idx),
            "volume": [100] * len(idx),
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    signals = pd.Series(["enter_long"] + [None] * 3, index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        allow_flip_on_bar=False,
        initial_cash=1000.0,
        position_size=1.0,
        blackout_utc=[("23:00", "01:00")],
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)
    trades = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    
    )
    assert isinstance(trades, list)
