"""Comprehensive tests for CLI module to achieve 100% coverage."""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd


class TestCmdRunBacktestPaths:
    """Tests for cmd_run_backtest code paths."""

    def test_with_rmm_config_inline(self, tmp_path: Path) -> None:
        """Test with inline rmm config (lines 97-99)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "rmm": {
                "enabled": True,
                "timeframe": "1H",
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1.0},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [],
                "short_entry_rules": [],
                "short_exit_rules": [],
                "features": [],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.data.loader.load_instrument_data"
        ) as mock_load:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame(
                {
                    "open": [1.0],
                    "high": [1.05],
                    "low": [0.95],
                    "close": [1.02],
                    "volume": [100],
                },
                index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
            )
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_with_fast_mode_last_days(self, tmp_path: Path) -> None:
        """Test fast_mode last_days filtering (lines 183-184)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "fast_mode": {"last_days": 30},
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1.0},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [],
                "short_entry_rules": [],
                "short_exit_rules": [],
                "features": [],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.data.loader.load_instrument_data"
        ) as mock_load:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            # 60 days of data
            df = pd.DataFrame(
                {
                    "open": [1.0] * 100,
                    "high": [1.05] * 100,
                    "low": [0.95] * 100,
                    "close": [1.02] * 100,
                    "volume": [100] * 100,
                },
                index=pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC"),
            )
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_with_fast_mode_limit_bars(self, tmp_path: Path) -> None:
        """Test fast_mode limit_bars filtering (lines 186)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "fast_mode": {"limit_bars": 50},
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1.0},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [],
                "short_entry_rules": [],
                "short_exit_rules": [],
                "features": [],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.data.loader.load_instrument_data"
        ) as mock_load:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame(
                {
                    "open": [1.0] * 100,
                    "high": [1.05] * 100,
                    "low": [0.95] * 100,
                    "close": [1.02] * 100,
                    "volume": [100] * 100,
                },
                index=pd.date_range("2024-01-01", periods=100, freq="h", tz="UTC"),
            )
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_with_strategy_params(self, tmp_path: Path) -> None:
        """Test strategy_params override (lines 196-199)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "strategy_params": {"fast_ema": 5, "slow_ema": 20},
            "strategy": {
                "strategy_name": "Test",
                "parameters": {"fast_ema": 10},
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1.0},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [],
                "short_entry_rules": [],
                "short_exit_rules": [],
                "features": [],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.data.loader.load_instrument_data"
        ) as mock_load:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame(
                {
                    "open": [1.0],
                    "high": [1.05],
                    "low": [0.95],
                    "close": [1.02],
                    "volume": [100],
                },
                index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
            )
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_with_strategy_overrides_parameters(self, tmp_path: Path) -> None:
        """Test strategy_overrides parameters (lines 214-220)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "strategy_overrides": {"parameters": {"slope_filter": True}},
            "strategy": {
                "strategy_name": "Test",
                "parameters": {"slope_filter": False},
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1.0},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [],
                "short_entry_rules": [],
                "short_exit_rules": [],
                "features": [],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.data.loader.load_instrument_data"
        ) as mock_load:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame(
                {
                    "open": [1.0],
                    "high": [1.05],
                    "low": [0.95],
                    "close": [1.02],
                    "volume": [100],
                },
                index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
            )
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_with_strategy_overrides_features(self, tmp_path: Path) -> None:
        """Test strategy_overrides features (lines 214-220)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "strategy_overrides": {"features": {"ema_fast": {"period": 5}}},
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1.0},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [],
                "short_entry_rules": [],
                "short_exit_rules": [],
                "features": [
                    {"name": "ema_fast", "kind": "ema", "params": {"period": 10}}
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.data.loader.load_instrument_data"
        ) as mock_load:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            df = pd.DataFrame(
                {
                    "open": [1.0],
                    "high": [1.05],
                    "low": [0.95],
                    "close": [1.02],
                    "volume": [100],
                },
                index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
            )
            mock_load.return_value = (df, [])

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0


class TestAdditionalCoverage:
    """Additional tests for missing coverage."""

    def test_no_data_request_uses_default_df(self, tmp_path: Path) -> None:
        """Test when no data_request, uses default dataframe (lines 120-131)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "strategy": {
                "strategy_name": "test",
                "long_entry_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_below",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_data_processed_parquet_save_fails(self, tmp_path: Path) -> None:
        """Test exception when saving processed_data.parquet (lines 138-139)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "strategy": {
                "strategy_name": "test",
                "long_entry_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_below",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch("pandas.DataFrame.to_parquet") as mock_parquet:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            # Make parquet save fail
            mock_parquet.side_effect = Exception("Save failed")

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            # Should still succeed despite save failure
            assert result == 0

    def test_tuple_result_with_2_elements(self, tmp_path: Path) -> None:
        """Test backtest result tuple with 2 elements (lines 360-361)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "strategy": {
                "strategy_name": "test",
                "long_entry_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_below",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat

            # Return tuple with 2 elements (trades, exposure)
            mock_backtest.return_value = ([], [])

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0

    def test_monte_carlo_resimulation(self, tmp_path: Path) -> None:
        """Test Monte Carlo resimulation (lines 443-445)."""
        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "monte_carlo": {"mode": "bar_resimulation", "trials": 100},
            "strategy": {
                "strategy_name": "test",
                "long_entry_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_above",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
                "long_exit_rules": [
                    {
                        "all_of": [
                            {
                                "condition": "is_below",
                                "left": {"field": "close"},
                                "right": {"value": 1},
                            }
                        ]
                    }
                ],
            },
        }
        config_path.write_text(json.dumps(config))

        args = argparse.Namespace(demo=False, config=str(config_path), user="test")

        with patch("trading_platform.cli.initialize_run") as mock_init, patch(
            "trading_platform.cli.finalize_run"
        ), patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps.monte_carlo_resimulation"
        ) as mock_mc:
            run_path = tmp_path / "runs/test"
            run_path.mkdir(parents=True)
            mock_init.return_value = run_path

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {"trades": [], "equity_curve": [], "strategy_name": "Test", "initial_capital": 100000, "compiled_strategy": mock_strat, "feature_enriched_df": pd.DataFrame()}
            mock_mc.return_value = {"trials": 100}

            from trading_platform.cli import cmd_run_backtest

            result = cmd_run_backtest(args)

            assert result == 0
            mock_mc.assert_called_once()
