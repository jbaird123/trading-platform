# ORPHANED_TEST: This test does not seem to correspond to a requirement.
from __future__ import annotations

from datetime import datetime

import pandas as pd

from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _df() -> pd.DataFrame:
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    return pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "volume": [1, 1],
        },
        index=idx,
    )


def _strat() -> CompiledStrategy:
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


def test_rmm_blocks_disallowed_side_and_logs_skip():
    df = _df()
    sig = pd.Series(["long", "flat"], index=df.index)
    cfg = RunConfig(initial_cash=1000.0)
    rem = RiskExitManager(config={})

    # RMM context disallows 'long' at first bar
    rmm_ctx = {
        df.index[0]: {
            "label": "trend_down",
            "confidence": 0.9,
            "allowed_sides": ["short"],
            "policy": {"min_confidence": 0.5},
        }
    }
    trades, _exp, skips = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_strat(),
        config=cfg,
        rem=rem,
        rmm_context=rmm_ctx,
        return_skips=True,
    )
    assert len(trades) == 0
    assert any(s.get("reason_code") == "rmm_block" for s in skips)
    s0 = next(s for s in skips if s.get("reason_code") == "rmm_block")
    assert s0.get("regime", {}).get("label") == "trend_down"
    assert s0.get("policy_snapshot", {}).get("allowed_sides") == ["short"]
