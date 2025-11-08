"""Additional tests for sweeps.py to achieve 100% coverage."""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import yaml
from trading_platform.core.sweeps import _rmm_context, run_parameter_sweep
from trading_platform.regime_market_manager.models import RMMConfig


def _basic_strategy_cfg() -> dict[str, Any]:
    rule_above = {
        "condition": "is_above",
        "left": {"ref": "ema_fast"},
        "right": {"value": 0},
    }
    rule_below = {
        "condition": "is_below",
        "left": {"ref": "ema_fast"},
        "right": {"value": 0},
    }
    base_rules = [{"any_of": [rule_above]}]
    short_rules = [{"any_of": [rule_below]}]
    features = [
        {
            "name": "ema_fast",
            "type": "EMA",
            "params": {"length": 5},
            "source": "close",
        },
        {
            "name": "ema_slow",
            "type": "EMA",
            "params": {"length": 10},
            "source": "close",
        },
    ]
    return {
        "strategy_name": "TestStrategy",
        "features": features,
        "long_entry_rules": base_rules,
        "long_exit_rules": short_rules,
        "short_entry_rules": short_rules,
        "short_exit_rules": base_rules,
        "parameters": {},
    }


def _mock_run_result(
    trades: list[Any],
    df: pd.DataFrame,
    *,
    compiled_strategy: Any | None = None,
    feature_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    return {
        "trades": trades,
        "feature_enriched_df": feature_df.copy()
        if feature_df is not None
        else df.copy(),
        "compiled_strategy": compiled_strategy or SimpleNamespace(features=[]),
    }


def _strategy_cfg_clone() -> dict[str, Any]:
    return deepcopy(_basic_strategy_cfg())


def _volume_strategy_cfg() -> dict[str, Any]:
    return {
        "strategy_name": "VolumeStrategy",
        "features": [],
        "long_entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"field": "volume"},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": {"field": "volume"},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        "short_entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": {"field": "volume"},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        "short_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"field": "volume"},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
    }


@pytest.fixture(autouse=True)
def _stub_run_backtest(monkeypatch):
    def _stub(**kwargs):
        df = kwargs.get("market_data")
        if df is None:
            df = pd.DataFrame()
        return _mock_run_result([], df)

    monkeypatch.setattr("trading_platform.core.sweeps.run_backtest", _stub)


def test_rmm_context_with_data_handler_cache_hit():
    """Test _rmm_context returns cached context from DataHandler."""
    # Validates: Lines 46-48 - DataHandler cache retrieval
    df = pd.DataFrame(
        {"close": [1.0, 1.1, 1.2]},
        index=pd.date_range("2024-01-01", periods=3, freq="D"),
    )

    rmm_cfg = {
        "policy": {},
        "timeframe": "1D",
        "regimes": [
            {
                "label": "cached",
                "confidence": 0.5,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 0.0,
                        }
                    ]
                },
            }
        ],
    }

    # Mock DataHandler with cached context
    mock_handler = Mock()
    cached_ctx = {datetime(2024, 1, 1): {"label": "cached", "confidence": 0.9}}
    mock_handler.get_rmm_context.return_value = cached_ctx
    # Mock get_data to return same-index df, so cache is used
    mock_handler.get_data.return_value = df.copy()

    cfg_raw = {"rmm_config": rmm_cfg}
    expected_cfg = RMMConfig(**rmm_cfg).model_dump(exclude_none=True)  # type: ignore[arg-type]
    expected_cfg = RMMConfig(**rmm_cfg).model_dump(exclude_none=True)  # type: ignore[arg-type]
    expected_cfg = RMMConfig(**rmm_cfg).model_dump(exclude_none=True)  # type: ignore[arg-type]
    expected_cfg = RMMConfig(**rmm_cfg).model_dump(exclude_none=True)  # type: ignore[arg-type]

    with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
        result = _rmm_context(df, cfg_raw, data_handler=mock_handler)

        # Should return cached context
        assert result == cached_ctx
        mock_handler.get_rmm_context.assert_called_once_with(expected_cfg, "1D")
        # get_data is now called once to check if the df is the full dataset
        mock_handler.get_data.assert_called_once_with(timeframe="1D")
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
        "policy": {"min_confidence": 0.5},
        "timeframe": "1D",
        "features": [
            {
                "name": "sma_short",
                "type": "SMA",
                "params": {"length": 3},
                "source": "close",
            }
        ],
        "regimes": [
            {
                "label": "bullish",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 0.0,
                        }
                    ]
                },
            }
        ],
    }

    # Mock DataHandler - cache miss
    mock_handler = Mock()
    mock_handler.get_rmm_context.return_value = None  # Cache miss
    # Mock get_data to return the full dataset (for cache check)
    mock_handler.get_data.return_value = df.copy()

    cfg_raw = {"rmm_config": rmm_cfg}
    expected_cfg = RMMConfig(**rmm_cfg).model_dump(exclude_none=True)  # type: ignore[arg-type]

    with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        # Mock regime classification
        regimes = pd.DataFrame(
            {"label": ["bullish"], "confidence": [0.9], "volume": [330]},
            index=pd.date_range("2024-01-01", periods=1, freq="D"),
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

        # Should have called get_data to check for full dataset
        mock_handler.get_data.assert_called_once_with(timeframe="1D")

        # Should call classify_regime with df and already_resampled=False
        mock_engine.classify_regime.assert_called_once_with(
            df, timeframe="1D", already_resampled=False
        )

        # Should have cached the result
        mock_handler.set_rmm_context.assert_called_once_with(
            expected_cfg,
            "1D",
            result,
        )
        mock_engine_class.assert_called_once()
        called_cfg = mock_engine_class.call_args.kwargs["config"]
        assert isinstance(called_cfg, RMMConfig)
        assert called_cfg.model_dump(exclude_none=True) == expected_cfg
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
        "strategy_name": "test_strategy",
        "features": [],
        "long_entry_rules": [],
        "long_exit_rules": [],
        "short_entry_rules": [],
        "short_exit_rules": [],
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
            "strategy_name": "old_strategy",
            "features": [],
            "long_entry_rules": [],
            "long_exit_rules": [],
            "short_entry_rules": [],
            "short_exit_rules": [],
            "parameters": {"should": "be_replaced"},
        }

        grid = {"param1": [1, 2]}

        with patch("trading_platform.core.sweeps.run_backtest") as mock_run:

            def _assert_strategy(**kwargs):
                scfg = kwargs.get("strategy_config") or {}
                assert scfg.get("strategy_name") == "test_strategy"
                return _mock_run_result([], df)

            mock_run.side_effect = _assert_strategy

            run_parameter_sweep(df, base_cfg, strategy_cfg_original, grid=grid)

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
        "strategy_name": "json_strategy",
        "features": [],
        "long_entry_rules": [],
        "long_exit_rules": [],
        "short_entry_rules": [],
        "short_exit_rules": [],
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

        strategy_cfg_original = {
            "strategy_name": "should_be_ignored",
            "features": [],
            "long_entry_rules": [],
            "long_exit_rules": [],
            "short_entry_rules": [],
            "short_exit_rules": [],
        }
        grid = {"param1": [1]}

        with patch("trading_platform.core.sweeps.run_backtest") as mock_run:

            def _assert_strategy(**kwargs):
                scfg = kwargs.get("strategy_config") or {}
                assert scfg.get("strategy_name") == "json_strategy"
                return _mock_run_result([], df)

            mock_run.side_effect = _assert_strategy

            run_parameter_sweep(df, base_cfg, strategy_cfg_original, grid=grid)

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

        strategy_cfg = _basic_strategy_cfg()

        grid = {
            "ema_fast_length": [5, 10],
            "ema_slow_length": [20, 30],
        }

        with patch("trading_platform.core.sweeps.run_backtest") as mock_run_backtest:
            mock_strategy = Mock()
            mock_strategy.features = [Mock(), Mock()]
            feature_df = pd.DataFrame(
                {"ema_fast": [1.0, 1.1], "ema_slow": [1.01, 1.11]}, index=df.index
            )
            mock_trade = Mock()
            mock_trade.pnl = 100.0
            mock_run_backtest.return_value = {
                "trades": [mock_trade],
                "feature_enriched_df": feature_df,
                "compiled_strategy": mock_strategy,
            }

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

        strategy_cfg = _basic_strategy_cfg()
        grid = {"param1": [1]}

        with patch(
            "trading_platform.core.sweeps.run_backtest"
        ) as mock_run_backtest, patch(
            "pathlib.Path.mkdir",
            side_effect=Exception("Permission denied"),
        ):
            mock_run_backtest.return_value = _mock_run_result([], df)

            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            assert result is not None
            assert "top" in result


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

        strategy_cfg = _basic_strategy_cfg()
        grid = {"param1": [1]}

        with patch("trading_platform.core.sweeps.run_backtest") as mock_run_backtest:
            compiled_strategy = SimpleNamespace(features=[])
            mock_run_backtest.return_value = _mock_run_result(
                [], df, compiled_strategy=compiled_strategy, feature_df=None
            )

            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            assert result is not None
            assert "top" in result
            assert (debug_path / "sweep_debug.log").exists()


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

        strategy_cfg = _basic_strategy_cfg()
        grid = {
            "ema_fast_length": [5],
            "ema_slow_length": [20],
        }

        with patch("trading_platform.core.sweeps.run_backtest") as mock_run_backtest:
            compiled_strategy = SimpleNamespace(features=[Mock(), Mock()])
            mock_run_backtest.return_value = _mock_run_result(
                [], df, compiled_strategy=compiled_strategy, feature_df=None
            )

            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            assert result is not None
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

        strategy_cfg = _basic_strategy_cfg()
        grid = {
            "ema_fast_length": [5],
            "ema_slow_length": [20],
        }

        with patch("trading_platform.core.sweeps.run_backtest") as mock_run_backtest:
            feature_df = pd.DataFrame(
                {"rsi": [50.0, 55.0], "macd": [0.1, 0.2]}, index=df.index
            )
            compiled_strategy = SimpleNamespace(features=[{"name": "rsi"}])
            mock_run_backtest.return_value = _mock_run_result(
                [], df, compiled_strategy=compiled_strategy, feature_df=feature_df
            )

            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid,
                debug_dir=debug_path,
            )

            assert result is not None
            log_content = (debug_path / "sweep_debug.log").read_text()
            assert "feat_df.shape=" in log_content
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

    strategy_cfg = _basic_strategy_cfg()

    perturbation = {
        "mode": "block",
        "std_pct": 0.05,
        "block_len": 5,
    }

    mock_trade = Mock()
    mock_trade.pnl = 50.0
    mock_trade.cost_currency = 0.0

    with patch(
        "trading_platform.core.sweeps.run_backtest",
        return_value=_mock_run_result([mock_trade], df),
    ) as mock_run:
        result = monte_carlo_resimulation(
            df,
            base_cfg,
            strategy_cfg,
            trials=2,
            seed=42,
            mode="bar_bootstrap",
            perturbation=perturbation,
        )

        assert result is not None
        assert "final_equity" in result
        assert mock_run.call_count == 2


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

    strategy_cfg = _basic_strategy_cfg()

    # Use gaussian mode (not block) with perturbation
    perturbation = {
        "mode": "gaussian",  # Different from block mode
        "std_pct": 0.05,
    }

    mock_trade = Mock()
    mock_trade.pnl = 50.0
    mock_trade.cost_currency = 0.0

    with patch(
        "trading_platform.core.sweeps.run_backtest",
        return_value=_mock_run_result([mock_trade], df),
    ) as mock_run:
        result = monte_carlo_resimulation(
            df,
            base_cfg,
            strategy_cfg,
            trials=2,
            seed=42,
            mode="bar_bootstrap",
            perturbation=perturbation,
        )

        assert result is not None
        assert "final_equity" in result
        assert mock_run.call_count == 2
