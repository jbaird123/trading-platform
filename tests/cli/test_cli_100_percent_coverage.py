"""Tests to achieve 100% CLI coverage - all missing lines."""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest


class TestRMMPathLoading:
    """Test RMM path loading (lines 91-92)."""

    def test_rmm_loaded_from_rmm_path(self, tmp_path: Path) -> None:
        """Test loading RMM config from rmm_path file."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        rmm_path = tmp_path / "rmm_config.json"

        # Create valid RMM config per schema
        rmm_config = {
            "regimes": [
                {
                    "label": "trend_up",
                    "confidence": 0.9,
                    "conditions": {
                        "all_of": [{"condition": "is_above", "left": "close", "right": 50}]
                    },
                }
            ],
            "features": [
                {"name": "rsi", "type": "RSI", "params": {"length": 14}}
            ]
        }
        rmm_path.write_text(json.dumps(rmm_config))

        config = {
            "run_id": "test_rmm_path",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm_path": str(rmm_path),  # Lines 91-92
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0],
                "high": [1.05],
                "low": [0.95],
                "close": [1.02],
                "volume": [100],
            }, index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0


class TestRMMModeBranches:
    """Test RMM mode detection (lines 297-301, 314-323)."""

    def test_rmm_mode_both_sides(self, tmp_path: Path) -> None:
        """Test _mode function returns 'both' when both long and short (line 297)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_mode_both",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm_config": {
                "timeframe": "1H",  # Use hourly timeframe to match test data
                "regimes": [
                    {
                        "label": "range",  # Non-trend label → both sides
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]
                        },
                    }
                ],
                "features": [{"name": "rsi", "type": "RSI", "params": {"length": 14}}]
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
                "short_entry_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
                ],
                "short_exit_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0, 1.1, 1.0],
                "high": [1.05, 1.15, 1.05],
                "low": [0.95, 1.05, 0.95],
                "close": [1.02, 1.12, 1.02],
                "volume": [100, 100, 100],
            }, index=pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0

    def test_rmm_mode_long_only(self, tmp_path: Path) -> None:
        """Test _mode function returns 'long_only' (lines 298-299)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_mode_long",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm_config": {
                "timeframe": "1H",  # Use hourly timeframe to match test data
                "regimes": [
                    {
                        "label": "trend_up",  # Uses conventional mapping: ["long"]
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]
                        },
                    }
                ],
                "features": [{"name": "rsi", "type": "RSI", "params": {"length": 14}}]
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 100],
            }, index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0

    def test_rmm_mode_short_only(self, tmp_path: Path) -> None:
        """Test _mode function returns 'short_only' (lines 299-300)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_mode_short",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm_config": {
                "timeframe": "1H",  # Use hourly timeframe to match test data
                "regimes": [
                    {
                        "label": "trend_down",  # Uses conventional mapping: ["short"]
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]
                        },
                    }
                ],
                "features": [{"name": "rsi", "type": "RSI", "params": {"length": 14}}]
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
                "short_entry_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
                ],
                "short_exit_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 100],
            }, index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0

    def test_rmm_mode_blocked(self, tmp_path: Path) -> None:
        """Test _mode function returns 'blocked' (line 301)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_mode_blocked",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm_config": {
                "timeframe": "1H",  # Use hourly timeframe to match test data
                "regimes": [
                    {
                        "label": "volatile",  # Non-trend label
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]
                        },
                    }
                ],
                "policy": {
                    "block_labels": ["volatile"]  # Block this label to get empty allowed_sides
                },
                "features": [{"name": "rsi", "type": "RSI", "params": {"length": 14}}]
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 100],
            }, index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0

    def test_rmm_mode_transitions(self, tmp_path: Path) -> None:
        """Test RMM mode transitions creating spans (lines 314-323)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_transitions",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm_config": {
                "timeframe": "1H",  # Use hourly timeframe to match test data
                "regimes": [
                    {
                        "label": "trend_up",  # Long only
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [{"condition": "is_above", "left": "close", "right": 1.05}]
                        },
                    },
                    {
                        "label": "trend_down",  # Short only
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [{"condition": "is_below", "left": "close", "right": 1.05}]
                        },
                    }
                ]
                # No features - regimes only based on close price conditions
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
                "short_entry_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
                ],
                "short_exit_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            # Create data that crosses 1.05 threshold to trigger multiple transitions
            # close < 1.05 → trend_down (short_only)
            # close > 1.05 → trend_up (long_only)
            # Need at least 3 transitions to hit lines 315-321
            df = pd.DataFrame({
                "open": [1.0, 1.1, 1.0, 1.1, 1.0, 1.1],
                "high": [1.05, 1.15, 1.05, 1.15, 1.05, 1.15],
                "low": [0.95, 1.05, 0.95, 1.05, 0.95, 1.05],
                "close": [1.02, 1.10, 1.03, 1.11, 1.02, 1.10],  # down→up→down→up→down→up
                "volume": [100, 100, 100, 100, 100, 100],
            }, index=pd.date_range("2024-01-01", periods=6, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0


class TestParamsSnapshotElif:
    """Test params_snapshot elif branch (lines 377-379)."""

    def test_params_from_strategy_parameters_no_strategy_params(self, tmp_path: Path) -> None:
        """Test when NO strategy_params in config, use strategy.parameters."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_elif",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            # NO strategy_params key at all
            "strategy": {
                "strategy_name": "Test",
                "parameters": {"my_param": 99},  # This triggers lines 377-379
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0],
                "high": [1.05],
                "low": [0.95],
                "close": [1.02],
                "volume": [100],
            }, index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"))
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0


class TestDataQualityFlags:
    """Test dq_flags branch (line 381)."""

    def test_dq_with_loader_flags(self, tmp_path: Path) -> None:
        """Test when loader returns data quality flags (line 381)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_dq",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "data_request": {
                "symbol": "EURUSD",
                "timeframe": "1H",
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
                ],
                "long_exit_rules": [
                    {"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, \
             patch("trading_platform.cli.finalize_run"), \
             patch("trading_platform.cli.run_backtest") as mock_backtest, \
             patch("trading_platform.cli.compile_strategy") as mock_compile, \
             patch("trading_platform.data.loader.load_instrument_data") as mock_load:

            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame({
                "open": [1.0],
                "high": [1.05],
                "low": [0.95],
                "close": [1.02],
                "volume": [100],
            }, index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"))

            # Return with flags - triggers line 381
            flags = ["gap_detected", "low_volume"]
            mock_load.return_value = (df, flags)

            mock_strat = MagicMock()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = []

            result = cmd_run_backtest(args)
            assert result == 0


# Parameter sweep and walk-forward tests are integration tests that are better
# covered in their respective test files (test_sweeps.py, test_robustness.py)
# These lines (387, 411-430) require complex mocking of the entire backtest pipeline


class TestTrainModelFlag:
    """Test train_model flag (lines 501-509)."""

    def test_ai_diagnose_with_train_model_flag(self, tmp_path: Path) -> None:
        """Test cmd_ai_diagnose with --train-model flag (lines 501-509)."""
        from trading_platform.cli import cmd_ai_diagnose

        brief_path = tmp_path / "brief.json"
        brief_data = {
            "backtest": {
                "run_id": "test",
                "trades": [
                    {
                        "direction": "long",
                        "entry_time": "2024-01-01T00:00:00+00:00",
                        "entry_price": 1.0,
                        "exit_time": "2024-01-01T01:00:00+00:00",
                        "exit_price": 1.1,
                        "pnl": 100,
                    }
                ],
                "metrics": {"total_pnl": 100, "win_rate": 1.0},
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief_path.write_text(json.dumps(brief_data))

        args = argparse.Namespace(
            brief=str(brief_path),
            qualitative_report_path=None,
            qualitative_report=False,
            train_model=True,  # This is the correct attribute name
        )

        with patch("trading_platform.cli.DiagnosticSynthesisEngine") as mock_engine_cls, \
             patch("trading_platform.ai.lab.trainer.train_profitability_model") as mock_train, \
             patch("trading_platform.ai.lab.trainer.save_model") as mock_save:

            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.generate_report_markdown.return_value = "# Report"
            mock_engine.generate_report_json.return_value = json.dumps(
                {"recommendations": []}
            )

            mock_model = MagicMock()
            mock_features = ["feature1", "feature2"]
            mock_train.return_value = (mock_model, mock_features)

            result = cmd_ai_diagnose(args)
            assert result == 0

            # Verify train was called
            mock_train.assert_called_once_with(brief_data)
            assert mock_save.call_count == 1

