# Validates: [JSON-11.13]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from pytest import approx
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg


def _mk_df() -> pd.DataFrame:
    idx = [
        datetime(2023, 1, 1, 0, 0),
        datetime(2023, 1, 1, 1, 0),
        datetime(2023, 1, 1, 2, 0),
        datetime(2023, 1, 1, 3, 0),
    ]
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0, 101.0],
            "low": [99.0, 99.0, 99.0, 99.0],
            "close": [100.0, 110.0, 120.0, 130.0],
            "volume": [1, 1, 1, 1],
        },
        index=idx,
    )
    return df


def test_exposure_curve_tracks_gross_notional_per_bar():
    df = _mk_df()
    # long from bar 1 to bar 2; flat at bar 3
    sig = pd.Series(["flat", "long", "long", "flat"], index=df.index)
    config = RunConfig(initial_cash=1000.0, allow_flip_on_bar=False, warmup_bars=0)
    rem = RiskExitManager(config={})
    trades, curve = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
        return_exposure=True,
    )
    assert len(curve) == len(df)
    # Expected exposures: 0, |10000*110|, |10000*120|, 0
    expected = [0.0, 1_100_000.0, 1_200_000.0, 0.0]
    got = [v for _, v in curve]
    assert got == approx(expected)
