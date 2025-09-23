# Validates: [BT-7.10]
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
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
        parameters={},
    )


@pytest.mark.req_BT_7_10
def test_return_skips_without_exposure():
    idx = [datetime(2024, 1, 1, h) for h in range(1)]
    df = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}, index=idx
    )
    sig = pd.Series(["long"], index=df.index)
    config = RunConfig()
    rem = RiskExitManager(config={})
    trades, exposure, skipped = run_backtest(
        df,
        sig,
        strategy=_dummy_strategy(),
        config=config,
        rem=rem,
        return_exposure=False,
        return_skips=True,
    )
    assert exposure == [] and isinstance(skipped, list)
