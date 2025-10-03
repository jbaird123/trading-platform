"""Additional tests for sweeps.py to achieve 100% coverage."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import yaml
from trading_platform.core.sweeps import (
    _rmm_context,
    run_parameter_sweep,
)


def test_rmm_context_with_data_handler_cache_hit():
    """Test _rmm_context returns cached context from DataHandler."""
    # Validates: Lines 46-48 - DataHandler cache retrieval
    df = pd.DataFrame(
        {"close": [1.0, 1.1, 1.2]},
        index=pd.date_range("2024-01-01", periods=3, freq="D"),
    )

    rmm_cfg = {
        "engine_type": "test",
        "policy": {},
        "timeframe": "1D",
    }

    # Mock DataHandler with cached context
    mock_handler = Mock()
    cached_ctx = {datetime(2024, 1, 1): {"label": "cached", "confidence": 0.9}}
    mock_handler.get_rmm_context.return_value = cached_ctx

    cfg_raw = {"rmm_config": rmm_cfg}

    with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
        # Validate config should still be called
        mock_engine_class.validate_config = Mock()

        result = _rmm_context(df, cfg_raw, data_handler=mock_handler)

        # Should return cached context
        assert result == cached_ctx
        mock_handler.get_rmm_context.assert_called_once_with(rmm_cfg, "1D")
        # Engine should not be instantiated since we got cached result
        mock_engine_class.assert_not_called()


def test_rmm_context_with_data_handler_cache_miss():
    """Test _rmm_context computes and caches context when cache miss."""
    # Validates: Lines 55-56, 92 - DataHandler get_data and set_rmm_context
    df = pd.DataFrame(
        {"close": [1.0, 1.1, 1.2], "volume": [100, 110, 120]},
        index=pd.date_range("2024-01-01", periods=3, freq="h"),
    )

    rmm_cfg = {
        "engine_type": "test",
        "policy": {"min_confidence": 0.5},
        "timeframe": "1D",
        "features": [{"name": "volume"}],
    }

    # Mock DataHandler - cache miss, then provides resampled data
    mock_handler = Mock()
    mock_handler.get_rmm_context.return_value = None  # Cache miss

    # Resampled daily data
    df_daily = pd.DataFrame(
        {"close": [1.2], "volume": [330]},
        index=pd.date_range("2024-01-01", periods=1, freq="D"),
    )
    mock_handler.get_data.return_value = df_daily

    cfg_raw = {"rmm_config": rmm_cfg}

    with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        # Mock regime classification
        regimes = pd.DataFrame(
            {"label": ["bullish"], "confidence": [0.9], "volume": [330]},
            index=df_daily.index,
        )
        mock_engine.classify_regime.return_value = regimes

        # Mock projection to hourly
        proj = pd.DataFrame(
            {
                "label": ["bullish"] * 3,
                "confidence": [0.9] * 3,
                "allowed_sides": [["long", "short"]] * 3,
                "volume": [330] * 3,
            },
            index=df.index,
        )
        mock_engine.project_to_index.return_value = proj

        result = _rmm_context(df, cfg_raw, data_handler=mock_handler)

        # Should have called get_data for resampling
        mock_handler.get_data.assert_called_once_with(timeframe="1D")

        # Should have called classify_regime with already_resampled=True
        mock_engine.classify_regime.assert_called_once_with(
            df_daily, timeframe="1D", already_resampled=True
        )

        # Should have cached the result
        assert mock_handler.set_rmm_context.called
        assert result is not None
        assert len(result) == 3  # One entry per hour


def test_run_parameter_sweep_with_strategy_path():
    """Test run_parameter_sweep reloads strategy from file when
    strategy_path is provided."""
    # Validates: Lines 115-122 - Strategy reload from file
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2],
            "high": [1.05, 1.15, 1.25],
            "low": [0.95, 1.05, 1.15],
            "close": [1.02, 1.12, 1.22],
            "volume": [100, 110, 120],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="h"),
    )

    # Create temp strategy file (YAML)
    strategy_cfg_yaml = {
        "name": "test_strategy",
        "entry_signals": ["long"],
        "exit_signals": ["exit_long"],
        "parameters": {"original": "value"},
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as yaml_file:
        yaml.dump(strategy_cfg_yaml, yaml_file)
        yaml_path = yaml_file.name

    try:
        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
            "strategy_path": yaml_path,  # Triggers reload
        }

        # Original strategy config (should be overridden)
        strategy_cfg_original = {
            "name": "old_strategy",
            "parameters": {"should": "be_replaced"},
        }

        grid = {"param1": [1, 2]}

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            mock_strategy = Mock()
            mock_strategy.generate_signals.return_value = pd.Series(
                [None, "long", "exit_long"], index=df.index
            )
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 100.0
            mock_backtest.return_value = [mock_trade]

            run_parameter_sweep(df, base_cfg, strategy_cfg_original, grid=grid)

            # Strategy should have been reloaded from YAML file, not using original
            assert mock_compile.called
            # Check that compiled strategy used reloaded config
            # (name should be test_strategy)
            call_args = mock_compile.call_args_list
            for call in call_args:
                scfg = call[0][0]
                assert scfg["name"] == "test_strategy"  # From YAML file

    finally:
        Path(yaml_path).unlink(missing_ok=True)


def test_run_parameter_sweep_with_strategy_path_json():
    """Test run_parameter_sweep reloads strategy from JSON file."""
    # Validates: Lines 115-122 - JSON strategy reload
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 110],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    strategy_cfg_json = {
        "name": "json_strategy",
        "entry_signals": ["long"],
        "parameters": {},
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as json_file:
        json.dump(strategy_cfg_json, json_file)
        json_path = json_file.name

    try:
        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
            "strategy_path": json_path,  # JSON file
        }

        strategy_cfg_original = {"name": "should_be_ignored"}
        grid = {"param1": [1]}

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            mock_strategy = Mock()
            mock_strategy.generate_signals.return_value = pd.Series(
                [None, "long"], index=df.index
            )
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 50.0
            mock_backtest.return_value = [mock_trade]

            run_parameter_sweep(df, base_cfg, strategy_cfg_original, grid=grid)

            # Check JSON file was used
            call_args = mock_compile.call_args_list
            for call in call_args:
                scfg = call[0][0]
                assert scfg["name"] == "json_strategy"

    finally:
        Path(json_path).unlink(missing_ok=True)


def test_run_parameter_sweep_with_debug_dir():
    """Test run_parameter_sweep debug logging to file."""
    # Validates: Lines 192-196, 211-212, 232-261 - Debug logging blocks
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 110],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        debug_path = Path(temp_dir) / "debug"

        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {
            "name": "test",
            "entry_signals": ["long"],
            "features": [
                {"name": "ema_fast", "params": {"period": 5}},
                {"name": "ema_slow", "params": {"period": 10}},
            ],
            "parameters": {},
        }

        grid = {
            "ema_fast_length": [5, 10],
            "ema_slow_length": [20, 30],
        }

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            # Create mock strategy with features
            mock_strategy = Mock()
            mock_strategy.name = "test"
            mock_strategy.features = [Mock(), Mock()]

            # Create mock feature dataframe with EMA columns
            feature_df = pd.DataFrame(
                {
                    "ema_fast": [1.0, 1.1],
                    "ema_slow": [1.01, 1.11],
                },
                index=df.index,
            )
            mock_strategy._feature_df = feature_df

            mock_signals = pd.Series([None, "long"], index=df.index)
            mock_strategy.generate_signals.return_value = mock_signals
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 100.0
            mock_backtest.return_value = [mock_trade]

            run_parameter_sweep(
                df,
                base_cfg,
                strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            # Check debug files were created
            assert debug_path.exists()
            log_file = debug_path / "sweep_debug.log"
            assert log_file.exists()

            # Check log contents
            log_content = log_file.read_text()
            assert "COMPILE params=" in log_content
            assert "COMPILED strategy:" in log_content
            assert "DEBUG params=" in log_content
            assert "ema_fast non-NaN count=" in log_content
            assert "ema_slow non-NaN count=" in log_content

            # Check that signal and feature parquet files were created
            parquet_files = list(debug_path.glob("*.parquet"))
            # Should have signals and features for each grid combination
            assert len(parquet_files) >= 4  # 2x2 grid = 4 combinations * 2 files each


def test_run_parameter_sweep_debug_dir_exception_handling():
    """Test debug logging handles exceptions gracefully."""
    # Validates: Lines 195-196 - Exception handling in debug logging
    df = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.05],
            "low": [0.95],
            "close": [1.02],
            "volume": [100],
        },
        index=pd.date_range("2024-01-01", periods=1, freq="h"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        debug_path = Path(temp_dir) / "debug"

        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {"name": "test", "entry_signals": ["long"]}
        grid = {"param1": [1]}

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            # Strategy that raises exception during feature access
            mock_strategy = Mock()
            mock_strategy.features = Mock(side_effect=Exception("Feature error"))
            mock_strategy.generate_signals.return_value = pd.Series(
                [None], index=df.index
            )
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 50.0
            mock_backtest.return_value = [mock_trade]

            # Should not raise exception despite feature access error
            result = run_parameter_sweep(
                df,
                base_cfg,
                strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            # Should still complete successfully
            assert result is not None
            assert "top" in result

            # Log should contain error message
            log_file = debug_path / "sweep_debug.log"
            if log_file.exists():
                log_content = log_file.read_text()
                assert "ERROR" in log_content or "error" in log_content.lower()


def test_run_parameter_sweep_debug_no_features():
    """Test debug logging when strategy has no features."""
    # Validates: Branch 209→212 - False branch (no features)
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 110],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        debug_path = Path(temp_dir) / "debug"

        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {"name": "test", "entry_signals": ["long"]}
        grid = {"param1": [1]}

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            # Strategy with NO features (or empty features list)
            mock_strategy = Mock()
            mock_strategy.name = "test"
            mock_strategy.features = []  # Empty features - triggers false branch
            mock_strategy._feature_df = None  # No feature dataframe

            mock_signals = pd.Series([None, "long"], index=df.index)
            mock_strategy.generate_signals.return_value = mock_signals
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 100.0
            mock_backtest.return_value = [mock_trade]

            result = run_parameter_sweep(
                df,
                base_cfg,
                strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            # Should complete successfully
            assert result is not None
            assert "top" in result

            # Log should still be created
            log_file = debug_path / "sweep_debug.log"
            assert log_file.exists()


def test_run_parameter_sweep_debug_no_feature_dataframe():
    """Test debug logging when strategy has no _feature_df."""
    # Validates: Branches 235→247, 256→266 - False branches (feat_df is None)
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 110],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        debug_path = Path(temp_dir) / "debug"

        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {"name": "test", "entry_signals": ["long"]}
        grid = {
            "ema_fast_length": [5],
            "ema_slow_length": [20],
        }

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            # Strategy with features but NO _feature_df
            mock_strategy = Mock()
            mock_strategy.name = "test"
            mock_strategy.features = [Mock(), Mock()]  # Has features
            mock_strategy._feature_df = (
                None  # But no feature dataframe - triggers false branches
            )

            mock_signals = pd.Series([None, "long"], index=df.index)
            mock_strategy.generate_signals.return_value = mock_signals
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 100.0
            mock_backtest.return_value = [mock_trade]

            result = run_parameter_sweep(
                df,
                base_cfg,
                strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            # Should complete successfully
            assert result is not None

            # Log should be created but not contain feature df info
            log_file = debug_path / "sweep_debug.log"
            assert log_file.exists()
            log_content = log_file.read_text()
            assert "DEBUG params=" in log_content


def test_run_parameter_sweep_debug_no_ema_columns():
    """Test debug logging when feature_df exists but has no ema columns."""
    # Validates: Branch 238→247 - False branch (no ema_fast/ema_slow columns)
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 110],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        debug_path = Path(temp_dir) / "debug"

        base_cfg = {
            "user_id": "test",
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {"name": "test", "entry_signals": ["long"]}
        grid = {
            "ema_fast_length": [5],
            "ema_slow_length": [20],
        }

        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_backtest:
            # Strategy with feature_df but NO ema columns
            mock_strategy = Mock()
            mock_strategy.name = "test"
            mock_strategy.features = [Mock()]

            # Feature dataframe with different columns (not ema_fast/ema_slow)
            feature_df = pd.DataFrame(
                {
                    "rsi": [50.0, 55.0],
                    "macd": [0.1, 0.2],
                },
                index=df.index,
            )
            mock_strategy._feature_df = feature_df  # Has df but no EMA columns

            mock_signals = pd.Series([None, "long"], index=df.index)
            mock_strategy.generate_signals.return_value = mock_signals
            mock_compile.return_value = mock_strategy

            mock_trade = Mock()
            mock_trade.pnl = 100.0
            mock_backtest.return_value = [mock_trade]

            result = run_parameter_sweep(
                df,
                base_cfg,
                strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            # Should complete successfully
            assert result is not None

            # Log should show feat_df.shape but not ema counts
            log_file = debug_path / "sweep_debug.log"
            assert log_file.exists()
            log_content = log_file.read_text()
            assert "feat_df.shape=" in log_content
            # Should NOT have ema count lines since columns don't exist
            assert "ema_fast non-NaN count=" not in log_content


def test_monte_carlo_resimulation_no_ohlc_columns():
    """Test monte_carlo_resimulation when dataframe has no OHLC columns."""
    # Validates: Branch 465→483 - False branch (no OHLC columns)
    from trading_platform.core.sweeps import monte_carlo_resimulation

    # DataFrame with only non-OHLC columns
    df = pd.DataFrame(
        {
            "volume": [100, 110, 120],
            "custom_indicator": [1.0, 1.1, 1.2],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="h"),
    )

    base_cfg = {
        "user_id": "test",
        "initial_cash": 10000.0,
        "position_size": 100.0,
        "instrument": {"symbol": "EURUSD"},
    }

    strategy_cfg = {"name": "test", "entry_signals": ["long"]}

    perturbation = {
        "mode": "block",
        "std_pct": 0.05,
        "block_len": 5,
    }

    with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile, patch(
        "trading_platform.core.sweeps.run_backtest"
    ) as mock_backtest:
        mock_strategy = Mock()
        mock_strategy.generate_signals.return_value = pd.Series(
            [None, "long", "exit_long"], index=df.index
        )
        mock_compile.return_value = mock_strategy

        mock_trade = Mock()
        mock_trade.pnl = 50.0
        mock_backtest.return_value = [mock_trade]

        # Should not crash even though there are no OHLC columns to perturb
        result = monte_carlo_resimulation(
            df,
            base_cfg,
            strategy_cfg,
            trials=2,
            seed=42,
            mode="bar_bootstrap",
            perturbation=perturbation,
        )

        # Should complete successfully
        assert result is not None
        assert "final_equity" in result


def test_monte_carlo_resimulation_gaussian_mode_no_ohlc():
    """Test monte_carlo_resimulation in gaussian mode with no OHLC columns."""
    # Validates: Branch 479→483 - False branch (no OHLC columns in gaussian mode)
    from trading_platform.core.sweeps import monte_carlo_resimulation

    # DataFrame with only non-OHLC columns
    df = pd.DataFrame(
        {
            "volume": [100, 110, 120],
            "custom_indicator": [1.0, 1.1, 1.2],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="h"),
    )

    base_cfg = {
        "user_id": "test",
        "initial_cash": 10000.0,
        "position_size": 100.0,
        "instrument": {"symbol": "EURUSD"},
    }

    strategy_cfg = {"name": "test", "entry_signals": ["long"]}

    # Use gaussian mode (not block) with perturbation
    perturbation = {
        "mode": "gaussian",  # Different from block mode
        "std_pct": 0.05,
    }

    with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile, patch(
        "trading_platform.core.sweeps.run_backtest"
    ) as mock_backtest:
        mock_strategy = Mock()
        mock_strategy.generate_signals.return_value = pd.Series(
            [None, "long", "exit_long"], index=df.index
        )
        mock_compile.return_value = mock_strategy

        mock_trade = Mock()
        mock_trade.pnl = 50.0
        mock_backtest.return_value = [mock_trade]

        # Should not crash even though there are no OHLC columns to perturb
        result = monte_carlo_resimulation(
            df,
            base_cfg,
            strategy_cfg,
            trials=2,
            seed=42,
            mode="bar_bootstrap",
            perturbation=perturbation,
        )

        # Should complete successfully
        assert result is not None
        assert "final_equity" in result
