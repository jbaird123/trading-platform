from __future__ import annotations

from datetime import datetime

import pandas as pd
from pytest import approx
from trading_platform.backtester.core import run_backtest
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        risk={},
    )


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
    trades, curve = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_dummy_strategy(),
        initial_cash=1000.0,
        stop_loss=None,
        take_profit=None,
        allow_flip_on_bar=False,
        warmup_bars=0,
        return_exposure=True,
    )
    assert len(curve) == len(df)
    # Expected exposures: 0, |10000*110|, |10000*120|, 0
    expected = [0.0, 1_100_000.0, 1_200_000.0, 0.0]
    got = [v for _, v in curve]
    assert got == approx(expected)
