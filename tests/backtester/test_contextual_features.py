"""Tests for contextual features in backtester."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
import yaml
from trading_platform.backtester.core import _run_backtest_simulation
from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy




def test_backtester_adds_contextual_features_to_trade_context() -> None:
    """Test that backtester computes and includes global features."""
    # Create sample market data with sufficient bars for ATR calculation
    idx = [datetime(2024, 1, 1, h) for h in range(20)]
    df_full = pd.DataFrame(
        {
            "open": [100.0 + i * 0.5 for i in range(20)],
            "high": [101.0 + i * 0.5 for i in range(20)],
            "low": [99.0 + i * 0.5 for i in range(20)],
            "close": [100.5 + i * 0.5 for i in range(20)],
            "volume": [1000] * 20,
        },
        index=idx,
    )
    # Mimic production trimming: drop the first 14 bars used for warmup
    df = df_full.iloc[14:].copy()

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
    strategy.generate_signals(df)  # Initialize _feature_df on trimmed data

    # Create signals with one entry near the middle of the trimmed window
    signals = pd.Series(
        [None] * 3 + ["enter_long"] + [None] * 2 + ["exit_long", None],
        index=df.index,
    )

    # Create temporary global.yaml with h1_atr feature
    with tempfile.TemporaryDirectory() as tmpdir:
        global_yaml_path = Path(tmpdir) / "config" / "features" / "global.yaml"
        global_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        global_yaml_path.write_text(
            yaml.dump(
                {
                    "features": [
                        {
                            "name": "h1_atr_14",
                            "type": "ATR",
                            "params": {"length": 14},
                            "timeframe": "1H",
                        }
                    ]
                }
            )
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            config = RunConfig.model_validate(
                {
                    "run_id": "test_contextual",
                    "instrument": {
                        "symbol": "EURUSD",
                        "timeframe": "1H",
                    },
                }
            )

            # Create a basic REM (risk exit manager)
            rem = RiskExitManager(
                config={"stop_loss": {"type": "offset", "price_offset": 0.0010}}
            )

            # Run backtest with explicit global features config path
            trades = _run_backtest_simulation(
                market_data=df,
                signals=signals,
                strategy=strategy,
                config=config,
                rem=rem,
                global_features_config_path=global_yaml_path,
            )

            # Assertions
            assert len(trades) > 0, "Expected at least one trade"
            first_trade = trades[0]

            assert hasattr(
                first_trade, "context_at_entry"
            ), "Trade missing context_at_entry"
            assert first_trade.context_at_entry is not None
            assert isinstance(first_trade.context_at_entry, dict)

            # Check for nested global_features structure
            assert "global_features" in first_trade.context_at_entry
            global_features = first_trade.context_at_entry["global_features"]
            assert isinstance(global_features, dict)

            # Check that h1_atr_14 exists in global_features
            assert "h1_atr_14" in global_features, "Global feature h1_atr_14 not found"

            h1_atr_value = global_features["h1_atr_14"]

            # Verify it's a number
            assert isinstance(
                h1_atr_value, (int, float)
            ), f"h1_atr_14 should be numeric, got {type(h1_atr_value)}"

            # Verify it's positive (ATR should always be positive)
            assert h1_atr_value > 0, f"Expected positive ATR, got {h1_atr_value}"
        finally:
            os.chdir(original_cwd)


def test_backtester_trade_context_with_multi_timeframe_at_entry_and_exit() -> None:
    """Test that multi-timeframe global features are captured at entry and exit.

    Configure global.yaml with h1_rsi feature, run a backtest on 15min data,
    and verify that both context_at_entry and context_at_exit contain the
    correctly calculated higher-timeframe feature.
    """
    # Create 15-minute data for 20 hours (80 bars) to get 20 1H bars
    # RSI(14) needs 14 bars, so we need at least 15 1H bars for valid RSI
    idx = pd.date_range(start="2024-01-01 00:00:00", periods=80, freq="15min")
    df_full = pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(80)],
            "high": [101.0 + i * 0.1 for i in range(80)],
            "low": [99.0 + i * 0.1 for i in range(80)],
            "close": [100.5 + i * 0.1 for i in range(80)],
            "volume": [1000] * 80,
        },
        index=idx,
    )
    df = df_full.iloc[56:].copy()  # Drop the first 14 1H bars (56 * 15min)

    # Create a simple strategy
    strategy = CompiledStrategy(
        name="test_mtf_strategy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    strategy.generate_signals(df)  # Initialize _feature_df on trimmed data

    signals = pd.Series(
        (
            [None] * 4
            + ["enter_long"]
            + [None] * 3
            + ["exit_long"]
            + [None] * (len(df) - 9)
        ),
        index=df.index,
    )

    # Create temporary global.yaml with h1_rsi feature
    with tempfile.TemporaryDirectory() as tmpdir:
        global_yaml_path = Path(tmpdir) / "config" / "features" / "global.yaml"
        global_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        global_yaml_path.write_text(
            yaml.dump(
                {
                    "features": [
                        {
                            "name": "h1_rsi_14",
                            "type": "RSI",
                            "params": {"length": 14},
                            "timeframe": "1H",
                        }
                    ]
                }
            )
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            config = RunConfig.model_validate(
                {
                    "run_id": "test_mtf_contextual",
                    "instrument": {
                        "symbol": "EURUSD",
                        "timeframe": "15min",
                    },
                }
            )

            # Create a basic REM
            rem = RiskExitManager(
                config={"stop_loss": {"type": "offset", "price_offset": 0.0010}}
            )

            # Run backtest with explicit global features path
            trades = _run_backtest_simulation(
                market_data=df,
                signals=signals,
                strategy=strategy,
                config=config,
                rem=rem,
                global_features_config_path=global_yaml_path,
            )

            # Assertions
            assert len(trades) > 0, "Expected at least one trade"
            first_trade = trades[0]

            # Compute expected 1H RSI values for verification
            from trading_platform.data.resample import resample_data
            from trading_platform.strategy.features import compute_features

            # Resample to 1H and compute RSI
            df_1h = resample_data(df, "1h")
            features_1h = compute_features(
                df_1h,
                [{"name": "h1_rsi_14", "type": "RSI", "params": {"length": 14}}],
            )
            # Forward-fill to base timeframe
            expected_rsi = features_1h["h1_rsi_14"].reindex(df.index, method="ffill")

            # Verify context_at_entry contains expected value
            assert hasattr(first_trade, "context_at_entry")
            assert first_trade.context_at_entry is not None
            assert isinstance(first_trade.context_at_entry, dict)
            assert "global_features" in first_trade.context_at_entry

            entry_features = first_trade.context_at_entry["global_features"]
            assert "h1_rsi_14" in entry_features

            h1_rsi_entry = entry_features["h1_rsi_14"]
            expected_entry_rsi = expected_rsi.iloc[64]
            assert h1_rsi_entry == expected_entry_rsi, (
                f"Entry RSI mismatch: got {h1_rsi_entry}, "
                f"expected {expected_entry_rsi}"
            )

            # Verify context_at_exit contains expected value
            assert hasattr(first_trade, "context_at_exit")
            assert first_trade.context_at_exit is not None
            assert isinstance(first_trade.context_at_exit, dict)
            assert "global_features" in first_trade.context_at_exit

            exit_features = first_trade.context_at_exit["global_features"]
            assert "h1_rsi_14" in exit_features

            h1_rsi_exit = exit_features["h1_rsi_14"]
            expected_exit_rsi = expected_rsi.iloc[68]
            assert h1_rsi_exit == expected_exit_rsi, (
                f"Exit RSI mismatch: got {h1_rsi_exit}, "
                f"expected {expected_exit_rsi}"
            )
        finally:
            os.chdir(original_cwd)


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

    # Create RunConfig without global features
    config = RunConfig.model_validate(
        {
            "run_id": "test_volume",
            "instrument": {
                "symbol": "EUR_USD",  # Use registered instrument
            },
        }
    )

    # Create a basic REM
    rem = RiskExitManager(
        config={"stop_loss": {"type": "offset", "price_offset": 0.0010}}
    )

    # Import test helper for empty global features
    from tests.test_helpers import get_empty_global_features_path

    # Run backtest with empty global features (only volume is added automatically)
    trades = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    )

    # Assertions
    assert isinstance(trades, list)
    assert len(trades) > 0, "Expected at least one trade"
    first_trade = trades[0]
    assert isinstance(first_trade, Trade)

    # Check that volume exists in nested global_features
    assert first_trade.context_at_entry is not None
    assert isinstance(first_trade.context_at_entry, dict)
    assert "global_features" in first_trade.context_at_entry
    global_features = first_trade.context_at_entry["global_features"]
    assert isinstance(global_features, dict)
    assert "volume" in global_features, "volume not in global_features"

    # Verify the volume value matches the entry bar
    # Entry is at bar 15 (index 15), volume should be 1000 + 15*100 = 2500
    expected_volume = 1000 + 15 * 100
    actual_volume = global_features["volume"]
    assert (
        actual_volume == expected_volume
    ), f"Expected volume {expected_volume}, got {actual_volume}"
