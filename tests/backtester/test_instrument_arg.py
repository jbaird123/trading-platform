from datetime import datetime
from typing import Any, cast

import pandas as pd
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg as dummy_strategy
from tests.test_helpers import (
    get_empty_global_features_path,
    run_backtest_simulation,
)


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
    strategy = dummy_strategy()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    signals = pd.Series(["enter_long", "exit_long"], index=df.index)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        pm_limits={"max_open_long": 0},  # Force a skip
        instrument={"symbol": "GBPUSD"},  # Use a non-default symbol
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    result = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    # Extract skipped from result, ignoring other return values
    _, _, skipped = cast(
        tuple[list[Any], list[tuple[datetime, float]], list[dict[str, Any]]], result
    )

    assert isinstance(skipped, list)
    assert len(skipped) > 0
    # This assertion will fail because the symbol is hardcoded to EURUSD
    assert skipped[0]["symbol"] == "GBPUSD"
