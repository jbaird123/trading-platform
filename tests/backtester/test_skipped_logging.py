# Validates: [BT-7.10]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg


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


def test_skip_logged_for_blackout():
    df = _df()
    sig = pd.Series(["long", "flat", "flat"], index=df.index)
    config = RunConfig(initial_cash=1000.0, blackout_utc=[("00:00", "00:30")])
    rem = RiskExitManager(config={})
    trades, _exp, skips = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    assert len(skips) >= 1
    s0 = skips[0]
    assert s0["reason_code"] in ("blackout_static", "blackout")
    assert "policy_snapshot" in s0


def test_skip_logged_for_position_cap():
    df = _df()
    sig = pd.Series(["long", "long", "flat"], index=df.index)
    config = RunConfig(
        initial_cash=1000.0, pm_limits={"max_open_long": 1, "max_open_short": 1}
    )
    rem = RiskExitManager(config={})
    trades, _exp, skips = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    # One entry, second long should be skipped due to cap
    assert any(s.get("reason_code") == "position_cap" for s in skips)
