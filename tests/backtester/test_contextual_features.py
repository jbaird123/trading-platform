"""Tests for contextual features in backtester."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def test_backtester_adds_contextual_features_to_trade_context() -> None:
    """Test that backtester computes and includes contextual features."""
    # Create sample market data with sufficient bars for ATR calculation
    idx = [datetime(2024, 1, 1, h) for h in range(20)]
    df = pd.DataFrame(
        {
            "open": [100.0 + i * 0.5 for i in range(20)],
            "high": [101.0 + i * 0.5 for i in range(20)],
            "low": [99.0 + i * 0.5 for i in range(20)],
            "close": [100.5 + i * 0.5 for i in range(20)],
            "volume": [1000] * 20,
        },
        index=idx,
    )

    # Create a simple strategy that generates one trade
    strategy = CompiledStrategy(
        name="test_strategy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    strategy.generate_signals(df)  # Initialize _feature_df

    # Create signals with one entry at bar 15 and exit at bar 18
    signals = pd.Series(
        [None] * 15 + ["enter_long"] + [None] * 2 + ["exit_long", None],
        index=df.index,
    )

    # Create RunConfig with contextual_features
    config = RunConfig.model_validate(
        {
            "run_id": "test_contextual",
            "instrument": {
                "symbol": "TEST",
                "asset_class": "Stock",
                "point_value": 1.0,
                "tick_size": 0.01,
            },
            "contextual_features": [
                {"name": "ctx_atr", "type": "ATR", "params": {"length": 14}}
            ],
        }
    )

    # Create a basic REM (risk exit manager)
    rem = RiskExitManager(config={"stop_loss_points": 10.0})

    # Run backtest
    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
    )

    # Assertions
    assert len(trades) > 0, "Expected at least one trade"
    first_trade = trades[0]

    assert hasattr(first_trade, "context_at_entry"), "Trade missing context_at_entry"
    assert first_trade.context_at_entry is not None
    assert isinstance(first_trade.context_at_entry, dict)

    # Check for nested strategy_features structure
    assert "strategy_features" in first_trade.context_at_entry
    strategy_features = first_trade.context_at_entry["strategy_features"]
    assert isinstance(strategy_features, dict)

    # Check that ctx_atr exists in strategy_features
    assert "ctx_atr" in strategy_features, "Contextual feature ctx_atr not found"

    ctx_atr_value = strategy_features["ctx_atr"]

    # Verify it's a number
    assert isinstance(
        ctx_atr_value, (int, float)
    ), f"ctx_atr should be numeric, got {type(ctx_atr_value)}"

    # Verify it's positive (ATR should always be positive)
    assert ctx_atr_value > 0, f"Expected positive ATR, got {ctx_atr_value}"


def test_trade_context_always_includes_volume() -> None:
    """Test that volume is always included in trade context."""
    # Create sample market data with varying volume
    idx = [datetime(2024, 1, 1, h) for h in range(20)]
    df = pd.DataFrame(
        {
            "open": [100.0 + i * 0.5 for i in range(20)],
            "high": [101.0 + i * 0.5 for i in range(20)],
            "low": [99.0 + i * 0.5 for i in range(20)],
            "close": [100.5 + i * 0.5 for i in range(20)],
            "volume": [1000 + i * 100 for i in range(20)],  # Varying volume
        },
        index=idx,
    )

    # Create a simple strategy (no volume in features)
    strategy = CompiledStrategy(
        name="test_strategy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    strategy.generate_signals(df)

    # Create signals with one entry at bar 15 and exit at bar 18
    signals = pd.Series(
        [None] * 15 + ["enter_long"] + [None] * 2 + ["exit_long", None],
        index=df.index,
    )

    # Create RunConfig WITHOUT volume in contextual_features
    # Use empty list to override defaults
    config = RunConfig.model_validate(
        {
            "run_id": "test_volume",
            "instrument": {
                "symbol": "TEST",
                "asset_class": "Stock",
                "point_value": 1.0,
                "tick_size": 0.01,
            },
            "contextual_features": [],  # Empty - no contextual features
        }
    )

    # Create a basic REM
    rem = RiskExitManager(config={"stop_loss_points": 10.0})

    # Run backtest
    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
    )

    # Assertions
    assert isinstance(trades, list)
    assert len(trades) > 0, "Expected at least one trade"
    first_trade = trades[0]
    assert isinstance(first_trade, Trade)

    # Check that volume exists in nested strategy_features
    assert first_trade.context_at_entry is not None
    assert isinstance(first_trade.context_at_entry, dict)
    assert "strategy_features" in first_trade.context_at_entry
    strategy_features = first_trade.context_at_entry["strategy_features"]
    assert isinstance(strategy_features, dict)
    assert "volume" in strategy_features, "volume not in strategy_features"

    # Verify the volume value matches the entry bar
    # Entry is at bar 15 (index 15), volume should be 1000 + 15*100 = 2500
    expected_volume = 1000 + 15 * 100
    actual_volume = strategy_features["volume"]
    assert (
        actual_volume == expected_volume
    ), f"Expected volume {expected_volume}, got {actual_volume}"
