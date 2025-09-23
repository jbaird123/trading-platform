# Validates: [BT-7.11]
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from pytest import approx
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_with_tp


def _mk_df() -> pd.DataFrame:
    idx = [
        datetime(2023, 1, 1, 0, 0),
        datetime(2023, 1, 1, 1, 0),
        datetime(2023, 1, 1, 2, 0),
    ]
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [100.0, 103.0, 104.0],
            "low": [100.0, 99.0, 98.0],
            "close": [100.0, 101.0, 102.0],
            "volume": [1, 1, 1],
        },
        index=idx,
    )


@pytest.mark.req_BT_7_11
def test_counterfactual_for_blackout_skip_with_tp():
    df = _mk_df()
    sig = pd.Series(["long", "flat", "flat"], index=df.index)
    config = RunConfig(
        initial_cash=1000.0, blackout_utc=[("00:00", "00:30")], position_size=10000.0
    )
    rem = RiskExitManager(config={})
    trades, _exp, skips = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_dummy_strategy_with_tp(2.0),
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    assert skips and "cf_exit_time" in skips[0]
    # Entry at 100, TP 2 => pnl ~ 2 * size (size=10000)
    assert skips[0]["cf_pnl_currency"] == approx(2.0 * 10000)
