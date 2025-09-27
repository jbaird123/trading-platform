from datetime import datetime
from typing import Any, cast

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg as dummy_strategy


def test_backtester_uses_provided_instrument_symbol():
    """This test will fail until the backtester logic is fixed."""
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1.0] * 2,
            "high": [1.0] * 2,
            "low": [1.0] * 2,
            "close": [1.0] * 2,
            "volume": [1] * 2,
        },
        index=idx,
    )
    signals = pd.Series(["long", "long"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        pm_limits={"max_open_long": 0},  # Force a skip
        instrument={"symbol": "GBPUSD"},  # Use a non-default symbol
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=signals,
        strategy=dummy_strategy(),
        config=config,
        rem=rem,
        return_skips=True,
    )
    # Extract skipped from result, ignoring other return values
    skipped = cast(list[dict[str, Any]], result[-1])

    assert isinstance(skipped, list)
    assert len(skipped) > 0
    # This assertion will fail because the symbol is hardcoded to EURUSD
    assert skipped[0]["symbol"] == "GBPUSD"
