# Validates: [PM-5.7]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg


def test_position_cap_skips_same_direction_when_already_open():
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [1, 1],
        },
        index=idx,
    )
    sig = pd.Series(["long", "long"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
    )
    rem = RiskExitManager(config={})
    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, _, skipped = result  # type: ignore[misc]
    # With constant prices and no exits, there are no closed trades yet.
    # Second long should be skipped due to position_cap.
    assert len(trades) == 0  # type: ignore[arg-type]
    assert skipped is not None
    assert any(s.get("reason_code") == "position_cap" for s in skipped)  # type: ignore[union-attr]
