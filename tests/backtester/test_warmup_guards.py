"""Warmup validation tests for the backtester."""

from __future__ import annotations

from datetime import datetime
from typing import cast

import pandas as pd
import pytest
from trading_platform.backtester.core import _run_backtest_simulation
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy

from tests.test_helpers import get_empty_global_features_path


def _basic_df(rows: int) -> pd.DataFrame:
    """Create a simple OHLCV dataframe with hourly bars."""
    index = pd.date_range(start=datetime(2023, 1, 1), periods=rows, freq="1h")
    return pd.DataFrame(
        {
            "open": [1.0] * rows,
            "high": [1.1] * rows,
            "low": [0.9] * rows,
            "close": [1.0] * rows,
            "volume": [100.0] * rows,
        },
        index=index,
    )


def _run_with_config(
    df: pd.DataFrame,
    *,
    strategy_config: dict[str, object],
    global_features_config_path: str | None = None,
) -> None:
    """Execute the backtester and return trades."""
    strategy = compile_strategy(strategy_config)
    signals = strategy.generate_signals(df)
    config = RunConfig.model_validate(
        {
            "run_id": "warmup_guard_test",
            "instrument": {"symbol": "EURUSD", "timeframe": "1H"},
        }
    )
    rem = RiskExitManager(config=None, instrument={"symbol": "EURUSD"})

    _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=global_features_config_path,
        return_exposure=False,
        return_skips=False,
    )


@pytest.mark.req_BT_7_7
def test_strategy_features_must_be_warmed() -> None:
    """Backtest must fail if strategy indicators still have NaNs."""
    df = _basic_df(5)  # Not enough bars for EMA length 10
    strategy_config = cast(
        dict[str, object],
        {
            "strategy_name": "ema_test",
            "features": [
                {"name": "sma_10", "type": "SMA", "params": {"length": 10}},
            ],
            "long_entry_rules": [
                {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"field": "close"},
                            "right": {"value": 0},
                        }
                    ]
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="Strategy features"):
        _run_with_config(
            df,
            strategy_config=strategy_config,
            global_features_config_path=get_empty_global_features_path(),
        )


@pytest.mark.req_BT_7_7
def test_global_features_must_be_warmed(tmp_path) -> None:
    """Backtest must fail if global features contain NaNs."""
    df = _basic_df(10)  # Not enough bars for ATR length 14
    strategy_config = cast(
        dict[str, object],
        {
            "strategy_name": "no_features",
            "features": [],
            "long_entry_rules": [
                {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"field": "close"},
                            "right": {"value": 0},
                        }
                    ]
                }
            ],
        },
    )

    features_dir = tmp_path / "config" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    global_yaml = features_dir / "global.yaml"
    global_yaml.write_text(
        "features:\n"
        '  - name: "h1_sma_20"\n'
        '    type: "SMA"\n'
        '    params: { "length": 20 }\n'
        '    timeframe: "1H"\n'
    )

    with pytest.raises(ValueError, match="Global features"):
        _run_with_config(
            df,
            strategy_config=strategy_config,
            global_features_config_path=str(global_yaml),
        )
