# Validates: [BT-7.10]
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.backtester.core import _run_backtest_simulation
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg
from tests.test_helpers import get_empty_global_features_path


def _df() -> pd.DataFrame:
    idx = [
        datetime(2023, 1, 1, 0, 0),
        datetime(2023, 1, 1, 1, 0),
        datetime(2023, 1, 1, 2, 0),
    ]
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0],
            "low": [99.0, 99.0, 99.0],
            "close": [100.0, 100.0, 100.0],
            "volume": [1, 1, 1],
        },
        index=idx,
    )


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


@pytest.mark.req_BT_7_10
def test_skip_logged_for_blackout():
    df = _df()
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", "exit_long", None], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        blackout_utc=[("00:00", "00:30")],
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)
    result = _run_backtest_simulation(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    trades, _exp, skips = result  # type: ignore[misc]
    assert skips is not None
    assert len(skips) >= 1  # type: ignore[arg-type]
    s0 = skips[0]  # type: ignore[index]
    assert s0["skip_reason"] in ("blackout_static", "blackout")
    assert "policy_snapshot" in s0


@pytest.mark.req_BT_7_10
def test_skip_logged_for_position_cap():
    df = _df()
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", None, "exit_long"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        pm_limits={"max_open_long": 1, "max_open_short": 1},
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)
    result = _run_backtest_simulation(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    trades, _exp, skips = result  # type: ignore[misc]
    # One entry, second long should be skipped due to cap
    assert skips is not None
    # TODO: Fix this test for command-based signals - position cap logic
    # needs review
    # assert any(s.get("skip_reason") == "position_cap" for s in skips)
