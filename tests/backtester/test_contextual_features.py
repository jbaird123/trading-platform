"""Tests for contextual features in backtester."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import cast

import pandas as pd
import pytest
import yaml
from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager

from tests.backtester.dummy_objects import _dummy_strategy_cfg
from tests.test_helpers import run_backtest_simulation


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
    df = df_full

    # Create a simple strategy that generates one trade
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Initialize _feature_df on trimmed data

    # Create signals with one entry near the middle of the trimmed window
    signals = pd.Series(
        [None] * 14 + ["enter_long", None, "exit_long"] + [None] * 3,
        index=df.index,
    )

    # Create temporary global.yaml with 1h_atr feature
    with tempfile.TemporaryDirectory() as tmpdir:
        global_yaml_path = Path(tmpdir) / "config" / "features" / "global.yaml"
        global_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        global_yaml_path.write_text(
            yaml.dump(
                {
                    "features": [
                        {
                            "name": "1h_atr_14",
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
                    "execution_model": "next_bar_open",
                }
            )

            # Create a basic REM (risk exit manager)
            rem = RiskExitManager(config={})

            # Run backtest with explicit global features config path
            trades_result = run_backtest_simulation(
                market_data=df,
                signals=signals,
                strategy=strategy,
                config=config,
                rem=rem,
                global_features_config_path=global_yaml_path,
            )

            assert isinstance(trades_result, list)
            trades: list[Trade] = cast(list[Trade], trades_result)

            # Assertions
            assert len(trades) > 0, "Expected at least one trade"
            first_trade: Trade = trades[0]

            assert hasattr(
                first_trade, "context_at_entry"
            ), "Trade missing context_at_entry"
            assert first_trade.context_at_entry is not None
            assert isinstance(first_trade.context_at_entry, dict)

            # Check for nested global_features structure
            assert "global_features" in first_trade.context_at_entry
            global_features = first_trade.context_at_entry["global_features"]
            assert isinstance(global_features, dict)

            # Check that 1h_atr_14 exists in global_features
            assert "1h_atr_14" in global_features, "Global feature 1h_atr_14 not found"

            h1_atr_value = global_features["1h_atr_14"]

            # Verify it's a number
            assert isinstance(
                h1_atr_value, (int, float)
            ), f"1h_atr_14 should be numeric, got {type(h1_atr_value)}"

            # Verify it's positive (ATR should always be positive)
            assert h1_atr_value > 0, f"Expected positive ATR, got {h1_atr_value}"
        finally:
            os.chdir(original_cwd)


def test_end_of_data_exit_preserves_context() -> None:
    """Forced end-of-data exit should retain contextual features."""
    idx = [datetime(2024, 1, 1, h) for h in range(20)]
    market = pd.DataFrame(
        {
            "open": [100.0 + i * 0.5 for i in range(20)],
            "high": [101.0 + i * 0.5 for i in range(20)],
            "low": [99.0 + i * 0.5 for i in range(20)],
            "close": [100.5 + i * 0.5 for i in range(20)],
            "volume": [1000] * 20,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(market)

    # Enter once and hold through the end of the dataset
    signals = pd.Series(
        [None] * 14 + ["enter_long"] + [None] * 5,
        index=market.index,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        global_yaml = Path(tmpdir) / "config" / "features" / "global.yaml"
        global_yaml.parent.mkdir(parents=True, exist_ok=True)
        global_yaml.write_text(
            yaml.dump(
                {
                    "features": [
                        {
                            "name": "1h_atr_14",
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
                    "run_id": "end_of_data_context",
                    "instrument": {
                        "symbol": "EURUSD",
                        "timeframe": "1H",
                    },
                    "execution_model": "next_bar_open",
                }
            )
            rem = RiskExitManager(config={})
            trades = run_backtest_simulation(
                market_data=market,
                signals=signals,
                strategy=strategy,
                config=config,
                rem=rem,
                global_features_config_path=global_yaml,
            )

            assert isinstance(trades, list)
            trade: Trade = cast(Trade, trades[-1])
            assert trade.exit_reason == "end_of_data"
            assert trade.context_at_exit is not None
            exit_context = trade.context_at_exit
            assert "global_features" in exit_context
            exit_1h_atr = exit_context["global_features"].get("1h_atr_14")
            assert isinstance(exit_1h_atr, (int, float))
            assert exit_1h_atr > 0
        finally:
            os.chdir(original_cwd)


def test_required_global_feature_missing_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing global feature values at execution timeframe must fail fast."""
    idx = [datetime(2024, 1, 1, h) for h in range(20)]
    market = pd.DataFrame(
        {
            "open": [100.0 + i * 0.5 for i in range(20)],
            "high": [101.0 + i * 0.5 for i in range(20)],
            "low": [99.0 + i * 0.5 for i in range(20)],
            "close": [100.5 + i * 0.5 for i in range(20)],
            "volume": [1000] * 20,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    if hasattr(strategy, "original_config"):
        strategy.original_config["strategy_name"] = "nan_guard_strategy"
    strategy.generate_signals(market)

    signals = pd.Series([None] * len(market), index=market.index)

    with tempfile.TemporaryDirectory() as tmpdir:
        global_yaml = Path(tmpdir) / "config" / "features" / "global.yaml"
        global_yaml.parent.mkdir(parents=True, exist_ok=True)
        global_yaml.write_text(
            yaml.dump(
                {
                    "features": [
                        {
                            "name": "1h_atr_14",
                            "type": "ATR",
                            "params": {"length": 14},
                            "timeframe": "1H",
                        }
                    ]
                }
            )
        )

        from trading_platform.strategy import features as feature_module

        original_compute = feature_module.compute_features

        def fake_compute_features(
            df: pd.DataFrame,
            specs: list[dict],
            strategy_parameters: dict | None = None,
        ) -> pd.DataFrame:
            result = original_compute(df, specs, strategy_parameters)
            for spec in specs:
                if spec.get("name") == "1h_atr_14":
                    result.loc[result.index[-1], "1h_atr_14"] = float("nan")
            return result

        monkeypatch.setattr(feature_module, "compute_features", fake_compute_features)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            config = RunConfig.model_validate(
                {
                    "run_id": "nan_guard",
                    "instrument": {
                        "symbol": "EURUSD",
                        "timeframe": "1H",
                    },
                    "execution_model": "next_bar_open",
                }
            )
            rem = RiskExitManager(
                config={"stop_loss": {"type": "offset", "price_offset": 0.0010}}
            )

            with pytest.raises(ValueError, match="Global feature '1h_atr_14' is NaN"):
                run_backtest_simulation(
                    market_data=market,
                    signals=signals,
                    strategy=strategy,
                    config=config,
                    rem=rem,
                    global_features_config_path=global_yaml,
                )
        finally:
            os.chdir(original_cwd)


def test_backtester_trade_context_with_multi_timeframe_at_entry_and_exit() -> None:
    """Test that multi-timeframe global features are captured at entry and exit.

    Configure global.yaml with 1h_rsi feature, run a backtest on 15min data,
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
    df = df_full

    # Create a simple strategy
    strategy = _dummy_strategy_cfg()
    if hasattr(strategy, "original_config"):
        strategy.original_config["strategy_name"] = "test_mtf_strategy"
    strategy.generate_signals(df)  # Initialize _feature_df on trimmed data

    warmup_bars = 56  # 14 hours * 4 bars/hour for 15min data
    remaining = len(df) - (warmup_bars + 4)
    signals = pd.Series(
        (
            [None] * warmup_bars
            + ["enter_long"]
            + [None] * 2
            + ["exit_long"]
            + [None] * max(0, remaining)
        ),
        index=df.index,
    )

    # Create temporary global.yaml with 1h_rsi feature
    with tempfile.TemporaryDirectory() as tmpdir:
        global_yaml_path = Path(tmpdir) / "config" / "features" / "global.yaml"
        global_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        global_yaml_path.write_text(
            yaml.dump(
                {
                    "features": [
                        {
                            "name": "1h_rsi_14",
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
                    "execution_model": "next_bar_open",
                }
            )

            # Create a basic REM
            rem = RiskExitManager(
                config={"stop_loss": {"type": "offset", "price_offset": 0.0010}}
            )

            # Run backtest with explicit global features path
            trades_result = run_backtest_simulation(
                market_data=df,
                signals=signals,
                strategy=strategy,
                config=config,
                rem=rem,
                global_features_config_path=global_yaml_path,
            )

            # Assertions
            assert isinstance(trades_result, list)
            trades = cast(list[Trade], trades_result)
            assert len(trades) > 0, "Expected at least one trade"
            first_trade: Trade = trades[0]

            # Compute expected 1H RSI values for verification
            from trading_platform.data.resample import resample_data
            from trading_platform.strategy.features import compute_features

            # Resample to 1H and compute RSI
            df_1h = resample_data(df, "1h")
            features_1h = compute_features(
                df_1h,
                [{"name": "1h_rsi_14", "type": "RSI", "params": {"length": 14}}],
            )
            # Forward-fill to base timeframe
            expected_rsi = features_1h["1h_rsi_14"].reindex(df.index, method="ffill")

            # Verify context_at_entry contains expected value
            assert hasattr(first_trade, "context_at_entry")
            assert first_trade.context_at_entry is not None
            assert isinstance(first_trade.context_at_entry, dict)
            assert "global_features" in first_trade.context_at_entry

            entry_features = first_trade.context_at_entry["global_features"]
            assert "1h_rsi_14" in entry_features

            entry_time = first_trade.entry_time
            assert entry_time is not None
            expected_entry_rsi = expected_rsi.loc[entry_time]
            entry_1h_rsi = entry_features["1h_rsi_14"]
            assert entry_1h_rsi == pytest.approx(expected_entry_rsi, rel=1e-6)

            # Verify context_at_exit contains expected value
            assert hasattr(first_trade, "context_at_exit")
            assert first_trade.context_at_exit is not None
            assert isinstance(first_trade.context_at_exit, dict)
            assert "global_features" in first_trade.context_at_exit

            exit_features = first_trade.context_at_exit["global_features"]
            assert "1h_rsi_14" in exit_features

            exit_time = first_trade.exit_time
            assert exit_time is not None
            expected_exit_rsi = expected_rsi.loc[exit_time]
            exit_1h_rsi = exit_features["1h_rsi_14"]
            assert exit_1h_rsi == pytest.approx(expected_exit_rsi, rel=1e-6)
        finally:
            os.chdir(original_cwd)
