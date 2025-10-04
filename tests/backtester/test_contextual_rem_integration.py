"""Integration test for contextual REM rules with Signal objects.

Task 3.1: End-to-end test of Signal context flowing to REM.
"""

from __future__ import annotations

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy


def test_contextual_rem_with_order_block_strategy():
    """
    Test full integration: Strategy emits Signals with context,
    backtester passes them to REM, REM uses context for exits.
    """
    # Define a simple order block strategy with context
    strategy_config = {
        "strategy_name": "Order Block Test",
        "features": [
            {
                "name": "ob_low",
                "type": "LLV",
                "params": {"length": 3},
                "source": "low",
            }
        ],
        "long_entry_rules": [
            {
                "all_of": [{"condition": "is_above", "left": "close", "right": 1.0}],
                "context": {"order_block_low": {"ref": "ob_low"}},
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    # Exit will be handled by REM, so use impossible condition
                    {"condition": "is_below", "left": "close", "right": 0.0}
                ]
            }
        ],
    }

    strategy = compile_strategy(strategy_config)

    # Define REM with reference_price rule
    rem_config = {
        "name": "Contextual Risk Test",
        "stop_loss": [
            {
                "type": "reference_price",
                "reference_point": "context.order_block_low",
                "offset": {"pips": -10},  # 10 pips below order block
            }
        ],
    }

    # EUR/USD instrument
    instrument = {
        "symbol": "EUR_USD",
        "pip_location": 0.0001,
        "point_value": 1.0,
    }

    rem = RiskExitManager(config=rem_config, instrument=instrument)

    # Create test data:
    # Bar 0: close=0.9, low=0.85 -> No entry
    # Bar 1: close=1.05, low=0.90 -> ob_low=0.85, enter long
    # Bar 2: close=1.10, low=0.95 -> ob_low=0.85, hold
    # Bar 3: close=0.80, low=0.84 -> Stop hit at 0.85-0.001=0.849
    market_data = pd.DataFrame(
        {
            "open": [0.88, 1.00, 1.08, 0.85],
            "high": [0.92, 1.08, 1.12, 0.88],
            "low": [0.85, 0.90, 0.95, 0.84],
            "close": [0.90, 1.05, 1.10, 0.85],
            "volume": [100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="h"),
    )

    run_config = RunConfig(
        user_id="test",
        run_id="ob_test",
        run_seed=42,
        log_level="INFO",
        allow_flip_on_bar=False,
        instrument=instrument,
        initial_cash=10000,
        position_size=1000,
    )

    # Generate signals from strategy
    signals = strategy.generate_signals(market_data)

    # run_backtest with return_exposure=True returns (trades, exposure)
    result = run_backtest(
        config=run_config,
        market_data=market_data,
        signals=signals,
        strategy=strategy,
        rem=rem,
        return_exposure=True,
    )

    # Type check: should be tuple of (trades, exposure)
    assert isinstance(result, tuple), "Expected tuple return"
    trades, _ = result  # type: ignore[misc]

    # Assertions
    assert len(trades) >= 1, "At least one trade should be generated"

    first_trade = trades[0]
    assert first_trade.side == "long"
    assert first_trade.exit_reason == "stop-loss"

    # The stop should be at ob_low (0.85) - 10 pips (0.001) = 0.849
    expected_stop = 0.85 - 0.001
    assert (
        abs(first_trade.exit_price - expected_stop) < 0.0001
    ), f"Expected stop at {expected_stop}, got {first_trade.exit_price}"
