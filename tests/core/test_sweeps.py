"""
Consolidated coverage and functional tests for trading_platform.core.sweeps.

Merged from test_sweeps_100_coverage.py, test_sweeps_coverage_gaps.py, and
test_parameter_sweep_full.py.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pandas as pd
import yaml
from trading_platform.core.sweeps import (
    _rmm_context,
    monte_carlo_resimulation,
    run_parameter_sweep,
    walk_forward_optimize_and_test,
)
from tests.test_helpers import create_market_data_with_warmup, get_empty_global_features_path
from trading_platform.regime_market_manager.models import RMMConfig

# --- test_sweeps_100_coverage.py ---

"""
Comprehensive test coverage for core/sweeps.py to achieve 100% coverage.

Targets all missing lines identified in the coverage report.
"""


class TestRmmContextCoverage:
    """Test _rmm_context function for missing coverage."""

    def test_rmm_context_with_yaml_and_json_extensions(self):
        """Test _rmm_context handles both .yaml and .yml extensions."""
        df = create_market_data_with_warmup(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
            freq="1D",
            include_global_features=False,
        )
        df = df[["close"]]  # Only need close for this test

        # Test .yml extension
        rmm_config = {
            "timeframe": "1D",
            "regimes": [
                {
                    "label": "test",
                    "confidence": 0.8,
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
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(rmm_config, f)
            yml_path = f.name

        try:
            cfg_raw = {"rmm_path": yml_path}
            with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
                mock_engine = Mock()
                mock_engine_class.return_value = mock_engine
                mock_daily = pd.DataFrame(
                    {"label": ["test"], "confidence": [0.8]},
                    index=pd.date_range("2024-01-01", periods=1, freq="D"),
                )
                mock_engine.classify_daily.return_value = mock_daily
                mock_proj = pd.DataFrame(
                    {"label": ["test"], "confidence": [0.8], "allowed_sides": [[]]},
                    index=df.index[:1],
                )
                mock_engine.project_to_index.return_value = mock_proj
                result = _rmm_context(df, cfg_raw)
                assert result is not None
        finally:
            Path(yml_path).unlink(missing_ok=True)


class TestParameterSweepCoverage:
    """Test run_parameter_sweep function for missing coverage."""

    def test_debug_logging_exception_handling(self):
        """Test exception handling in debug logging lines 114-115."""
        df = create_market_data_with_warmup(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 1, 2),
            freq="1H",
            include_global_features=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_cfg = {
                "user_id": "test_user",
                "initial_cash": 10000.0,
                "position_size": 100.0,
                "instrument": {"symbol": "EURUSD"},
            }
            strategy_cfg = {"entry_signals": ["long"]}

            # Create a mock trade with pnl
            mock_trade = Mock()
            mock_trade.pnl = 100.0

            with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
                mock_strat = Mock()
                mock_compile.return_value = mock_strat

                # Mock signals that will cause an exception in value_counts
                mock_sig = Mock()
                mock_sig.value_counts.side_effect = Exception("Test exception")
                mock_strat.generate_signals.return_value = mock_sig

                with patch(
                    "trading_platform.core.sweeps._run_backtest_simulation"
                ) as mock_backtest:
                    mock_backtest.return_value = [mock_trade]  # Returns trades directly

                    grid = {"param1": [1]}
                    result = run_parameter_sweep(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        grid=grid,
                        debug_dir=temp_dir,
                    )

                    # Should handle exception gracefully and continue
                    assert isinstance(result, dict)

    def test_objective_pnl_minus_dd_branch(self):
        """Test pnl_minus_dd objective branch line 147."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create mock trades that cause drawdown
        mock_trade1 = Mock()
        mock_trade1.pnl = -500.0  # Loss
        mock_trade2 = Mock()
        mock_trade2.pnl = 200.0  # Profit

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long", "short"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade1, mock_trade2]

                grid = {"param1": [1]}
                result = run_parameter_sweep(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    grid=grid,
                    objective="pnl_minus_dd",
                    dd_penalty=2.0,
                )

                assert isinstance(result, dict)
                # Score should be total_pnl - penalty * max_dd
                expected_score = -300.0 - 2.0 * 500.0  # Loss minus drawdown penalty
                assert result["top"]["score"] == expected_score

    def test_objective_pnl_dd_vol_with_empty_trades(self):
        """Test pnl_dd_vol objective with empty trades list lines 161, 165."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["flat"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = []  # Empty trades list

                grid = {"param1": [1]}
                result = run_parameter_sweep(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    grid=grid,
                    objective="pnl_dd_vol",
                    vol_penalty=0.5,
                )

                assert isinstance(result, dict)
                # With empty trades, std should be 0.0
                assert result["top"]["score"] == 0.0

    def test_objective_pnl_dd_vol_with_trades(self):
        """Test pnl_dd_vol objective with trades lines 172-174."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create mock trades with varying PnL for volatility calculation
        mock_trade1 = Mock()
        mock_trade1.pnl = 100.0
        mock_trade2 = Mock()
        mock_trade2.pnl = -50.0
        mock_trade3 = Mock()
        mock_trade3.pnl = 150.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade1, mock_trade2, mock_trade3]

                grid = {"param1": [1]}
                result = run_parameter_sweep(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    grid=grid,
                    objective="pnl_dd_vol",
                    vol_penalty=0.1,
                )

                assert isinstance(result, dict)
                # Should calculate volatility and apply penalty
                # The exact calculation depends on the drawdown penalty too
                assert "top" in result
                assert "score" in result["top"]
                # Just verify the score is reasonable (accounts for volatility penalty)
                assert result["top"]["score"] < 200.0  # Less than pure total PnL


class TestWalkForwardOptimizeCoverage:
    """Test walk_forward_optimize_and_test function for missing coverage."""

    def test_walk_forward_with_seed_line_200(self):
        """Test walk_forward with seed parameter to hit line 200."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2, 1.3, 1.4]},
            index=pd.date_range("2024-01-01", periods=5, freq="D"),
        )

        # Mock strategy compilation and backtesting
        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps._run_backtest_simulation"
        ) as mock_backtest, patch("random.seed") as mock_seed:
            mock_compile.return_value = Mock()
            mock_backtest.return_value = ([], 100.0)

            # Call with seed to hit line 200
            result = walk_forward_optimize_and_test(
                df=df,
                base_cfg={"instrument": {"symbol": "EURUSD"}},
                strategy_cfg={"name": "test"},
                grid={"test_param": [1]},
                window=2,
                step=1,
                seed=42,  # This should trigger random.seed(seed) on line 200
            )

            # Verify random.seed was called with the correct value
            mock_seed.assert_called_once_with(42)
            assert result is not None

    def test_walk_forward_with_tuple_return_line_200(self):
        """Test walk_forward handling tuple return from run_backtest line 200."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2, 1.3],
                "high": [1.05, 1.15, 1.25, 1.35],
                "low": [0.95, 1.05, 1.15, 1.25],
                "close": [1.02, 1.12, 1.22, 1.32],
                "volume": [100, 200, 300, 400],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        base_cfg = {
            "initial_cash": 10000.0,
            "user_id": "test",
            "instrument": {"symbol": "EURUSD"},
        }
        strategy_cfg = {"entry_signals": ["long"]}
        grid = {"param1": [1, 2]}

        mock_trade = Mock()
        mock_trade.pnl = 50.0

        with patch("trading_platform.core.sweeps.walk_forward_splits") as mock_splits:
            # Create a split
            mock_split = Mock()
            mock_split.train_start = df.index[0]
            mock_split.train_end = df.index[1]
            mock_split.test_start = df.index[2]
            mock_split.test_end = df.index[3]
            mock_splits.return_value = [mock_split]

            with patch(
                "trading_platform.core.sweeps.run_parameter_sweep"
            ) as mock_sweep:
                mock_sweep.return_value = {"top": {"params": {"param1": 2}}}

                with patch(
                    "trading_platform.core.sweeps.compile_strategy"
                ) as mock_compile:
                    mock_strat = Mock()
                    mock_compile.return_value = mock_strat
                    mock_strat.generate_signals.return_value = pd.Series(["long"])

                    with patch(
                        "trading_platform.core.sweeps._run_backtest_simulation"
                    ) as mock_backtest:
                        # Return tuple instead of list to test line 200
                        mock_backtest.return_value = ([mock_trade], [], [])

                        result = walk_forward_optimize_and_test(
                            df=df,
                            base_cfg=base_cfg,
                            strategy_cfg=strategy_cfg,
                            window=2,
                            step=1,
                            grid=grid,
                        )

                        assert isinstance(result, dict)
                        assert "splits" in result


class TestMonteCarloResimulationCoverage:
    """Test monte_carlo_resimulation function for missing coverage."""

    def test_monte_carlo_gaussian_perturbation_line_234(self):
        """Test Gaussian perturbation mode line 234."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Configure Gaussian perturbation
        perturbation = {"mode": "gaussian", "std_pct": 0.01}

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        # Add cost_currency attribute for cost jitter testing
        mock_trade.cost_currency = 5.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                    perturbation=perturbation,
                )

                assert isinstance(result, dict)
                assert result["trials"] == 1

    def test_monte_carlo_lines_286_289_302(self):
        """Test lines 286->289 and 302 in Monte Carlo."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Configure cost jitter to test lines 286-289
        cost_jitter = {
            "spread_jitter_pct": 0.1,
            "slippage_jitter_pct": 0.1,
            "per_trade_cost_jitter_pct": 0.1,
        }

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        mock_trade.cost_currency = 10.0  # For cost jitter calculation

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade]

                # Mock cfg.model_copy to test line 302
                mock_cfg = Mock()
                mock_cfg.initial_cash = 10000.0
                mock_cfg.cost_model = {
                    "spread_per_unit": 0.001,
                    "slippage_per_unit": 0.001,
                }
                mock_cfg.model_copy.return_value = mock_cfg

                with patch(
                    "trading_platform.core.sweeps.RunConfig.model_validate"
                ) as mock_validate:
                    mock_validate.return_value = mock_cfg

                    result = monte_carlo_resimulation(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        trials=1,
                        seed=42,
                        cost_jitter=cost_jitter,
                    )

                    assert isinstance(result, dict)

    def test_monte_carlo_lines_324_325_331_337(self):
        """Test equity curve calculation lines 324-325, 331, 337."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create trades with losses to test drawdown calculation
        mock_trade1 = Mock()
        mock_trade1.pnl = -200.0  # Loss to create drawdown
        mock_trade1.cost_currency = 0.0

        mock_trade2 = Mock()
        mock_trade2.pnl = -300.0  # Bigger loss
        mock_trade2.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade1, mock_trade2]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Should have negative equity due to losses
                assert result["final_equity"]["mean"] < 10000.0

    def test_monte_carlo_line_364_win_rate_calculation(self):
        """Test win rate calculation line 364."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Mix of winning and losing trades
        winning_trade = Mock()
        winning_trade.pnl = 100.0
        winning_trade.cost_currency = 0.0

        losing_trade = Mock()
        losing_trade.pnl = -50.0
        losing_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [winning_trade, losing_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Win rate should be 0.5 (1 win out of 2 trades)
                assert result["win_rate"]["mean"] == 0.5

    def test_monte_carlo_line_387_exemplars_handling(self):
        """Test exemplars handling line 387."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        mock_trade = Mock()
        mock_trade.pnl = 50.0
        mock_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=3,  # Multiple trials for exemplar sorting
                    seed=42,
                )

                assert isinstance(result, dict)
                assert "exemplars" in result
                assert "worst" in result["exemplars"]
                assert "median" in result["exemplars"]
                assert "best" in result["exemplars"]

    def test_monte_carlo_lines_432_442_467(self):
        """Test various percentile and aggregation lines 432, 442, 467."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create trades that will result in ruin (final equity <= 0)
        ruinous_trade = Mock()
        ruinous_trade.pnl = -11000.0  # More loss than initial cash
        ruinous_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [ruinous_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=2,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Should have non-zero ruin probability (line 432)
                assert result["ruin_prob"] > 0.0
                # Should have calculated CVaR (line 442)
                assert "risk" in result
                assert "cvar_95" in result["risk"]


class TestEdgeCasesAndHelperFunctions:
    """Test edge cases and helper functions for missing coverage."""

    def test_rmm_context_returns_none_for_invalid_config(self):
        """Test that _rmm_context returns None for invalid configurations."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="D")
        )

        # Test with string instead of dict
        cfg_raw = {"rmm_config": "invalid"}
        result = _rmm_context(df, cfg_raw)
        assert result is None

        # Test with None
        cfg_raw_none: dict[str, Any] = {"rmm_config": None}
        result = _rmm_context(df, cfg_raw_none)
        assert result is None

    def test_debug_dir_exception_handling_lines_114_115(self):
        """Test exception handling when creating debug directory fails lines 114-115."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = []

                # Mock Path.mkdir to raise an exception
                with patch(
                    "pathlib.Path.mkdir", side_effect=Exception("Permission denied")
                ):
                    grid = {"param1": [1]}
                    result = run_parameter_sweep(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        grid=grid,
                        debug_dir="/invalid/path",  # This should trigger exception
                    )

                    assert isinstance(result, dict)

    def test_objective_else_branch_line_165(self):
        """Test the else branch for unknown objective line 165."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        mock_trade = Mock()
        mock_trade.pnl = 50.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade]

                grid = {"param1": [1]}
                result = run_parameter_sweep(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    grid=grid,
                    objective="unknown_objective",  # This should trigger else branch
                )

                assert isinstance(result, dict)
                # Should fall back to total_pnl
                assert result["top"]["score"] == 50.0

    def test_debug_logging_with_hasattr_false_lines_172_174(self):
        """Test debug logging when signals don't have get method lines 172-174."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
            strategy_cfg = {"entry_signals": ["long"]}

            mock_trade = Mock()
            mock_trade.pnl = 50.0

            with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
                mock_strat = Mock()
                mock_compile.return_value = mock_strat

                # Create a mock signal that doesn't have proper value_counts behavior
                mock_sig = Mock()
                # Mock value_counts to return something that doesn't have get method
                mock_vc = Mock()
                del mock_vc.get  # Remove get method to test hasattr check
                mock_sig.value_counts.return_value = mock_vc
                mock_strat.generate_signals.return_value = mock_sig

                with patch(
                    "trading_platform.core.sweeps._run_backtest_simulation"
                ) as mock_backtest:
                    mock_backtest.return_value = [mock_trade]

                    grid = {"param1": [1]}
                    result = run_parameter_sweep(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        grid=grid,
                        debug_dir=temp_dir,
                    )

                    assert isinstance(result, dict)

    def test_parameter_sweep_empty_grid_and_random_space(self):
        """Test parameter sweep with empty grid and random_space."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["flat"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = []

                # No grid or random_space provided
                result = run_parameter_sweep(
                    df=df, base_cfg=base_cfg, strategy_cfg=strategy_cfg
                )

                assert isinstance(result, dict)
                # Should return default values for empty results
                assert result["top"]["score"] == 0.0

    def test_monte_carlo_with_empty_equity_vals(self):
        """Test Monte Carlo with empty equity values."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["flat"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                # Return empty trades list
                mock_backtest.return_value = []

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Should handle empty curves gracefully
                assert result["time_under_water_mean"] == 0.0

    def test_walk_forward_tuple_return_line_200(self):
        """Test walk_forward when run_backtest returns tuple line 200."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2, 1.3],
                "high": [1.05, 1.15, 1.25, 1.35],
                "low": [0.95, 1.05, 1.15, 1.25],
                "close": [1.02, 1.12, 1.22, 1.32],
                "volume": [100, 200, 300, 400],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        base_cfg = {
            "initial_cash": 10000.0,
            "user_id": "test",
            "instrument": {"symbol": "EURUSD"},
        }
        strategy_cfg = {"entry_signals": ["long"]}
        grid = {"param1": [1]}

        mock_trade = Mock()
        mock_trade.pnl = 50.0

        with patch("trading_platform.core.sweeps.walk_forward_splits") as mock_splits:
            mock_split = Mock()
            mock_split.train_start = df.index[0]
            mock_split.train_end = df.index[1]
            mock_split.test_start = df.index[2]
            mock_split.test_end = df.index[3]
            mock_splits.return_value = [mock_split]

            with patch(
                "trading_platform.core.sweeps.run_parameter_sweep"
            ) as mock_sweep:
                mock_sweep.return_value = {"top": {"params": {"param1": 1}}}

                with patch(
                    "trading_platform.core.sweeps.compile_strategy"
                ) as mock_compile:
                    mock_strat = Mock()
                    mock_compile.return_value = mock_strat
                    mock_strat.generate_signals.return_value = pd.Series(["long"])

                    with patch(
                        "trading_platform.core.sweeps._run_backtest_simulation"
                    ) as mock_backtest:
                        # Return tuple to test line 200
                        mock_backtest.return_value = ([mock_trade], [], [])

                        result = walk_forward_optimize_and_test(
                            df=df,
                            base_cfg=base_cfg,
                            strategy_cfg=strategy_cfg,
                            window=2,
                            step=1,
                            grid=grid,
                        )

                        assert isinstance(result, dict)

    def test_monte_carlo_cost_model_handling_lines_286_289_302(self):
        """Test Monte Carlo cost model handling lines 286->289, 302."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        # Mock RunConfig with proper cost_model
        mock_cfg = Mock()
        mock_cfg.initial_cash = 10000.0
        mock_cfg.cost_model = {"spread_per_unit": 0.001, "slippage_per_unit": 0.001}

        # Create a new mock for model_copy return
        mock_cfg_copy = Mock()
        mock_cfg_copy.initial_cash = 10000.0
        mock_cfg_copy.cost_model = {
            "spread_per_unit": 0.0011,
            "slippage_per_unit": 0.0011,
        }
        mock_cfg.model_copy.return_value = mock_cfg_copy

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        cost_jitter = {
            "spread_jitter_pct": 0.1,
            "slippage_jitter_pct": 0.1,
        }

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        mock_trade.cost_currency = 5.0

        with patch(
            "trading_platform.core.sweeps.RunConfig.model_validate"
        ) as mock_validate:
            mock_validate.return_value = mock_cfg

            with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
                mock_strat = Mock()
                mock_compile.return_value = mock_strat
                mock_strat.generate_signals.return_value = pd.Series(["long"])

                with patch(
                    "trading_platform.core.sweeps._run_backtest_simulation"
                ) as mock_backtest:
                    mock_backtest.return_value = [mock_trade]

                    result = monte_carlo_resimulation(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        trials=1,
                        seed=42,
                        cost_jitter=cost_jitter,
                    )

                    assert isinstance(result, dict)
                    # Verify model_copy was called for cost jitter
                    mock_cfg.model_copy.assert_called_once()

    def test_monte_carlo_equity_curve_branches_lines_324_325_331(self):
        """Test Monte Carlo equity curve calculation branches lines 324-325, 331."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create trades that will trigger various equity curve conditions
        profitable_trade = Mock()
        profitable_trade.pnl = 500.0  # Creates new peak
        profitable_trade.cost_currency = 0.0

        losing_trade = Mock()
        losing_trade.pnl = -200.0  # Creates drawdown
        losing_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [profitable_trade, losing_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Should have calculated drawdown from peak
                assert result["max_drawdown"]["mean"] >= 0

    def test_monte_carlo_tuw_and_win_rate_lines_364(self):
        """Test time under water and win rate calculation line 364."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        losing_trade = Mock()
        losing_trade.pnl = -100.0
        losing_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [losing_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                )

                assert isinstance(result, dict)
                # With losing trade, win rate should be 0
                assert result["win_rate"]["mean"] == 0.0
                # Time under water should be > 0 due to loss
                assert result["time_under_water_mean"] >= 0

    def test_monte_carlo_exemplars_empty_curves_line_387(self):
        """Test Monte Carlo with empty curves for exemplars line 387."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["flat"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = []  # No trades

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Should have exemplars with initial equity only
                assert "exemplars" in result
                assert "worst" in result["exemplars"]
                assert result["exemplars"]["worst"]["final_equity"] == 10000.0

    def test_monte_carlo_risk_calculations_lines_432_442_467(self):
        """Test risk calculations including VaR, CVaR, ruin prob lines 432, 442, 467."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create multiple trials with varied outcomes for risk calculation
        profitable_trade = Mock()
        profitable_trade.pnl = 100.0
        profitable_trade.cost_currency = 0.0

        losing_trade = Mock()
        losing_trade.pnl = -50.0
        losing_trade.cost_currency = 0.0

        ruinous_trade = Mock()
        ruinous_trade.pnl = -12000.0  # Causes ruin
        ruinous_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                # Simulate different outcomes across trials
                mock_backtest.side_effect = [
                    [profitable_trade],
                    [losing_trade],
                    [ruinous_trade],
                ]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=3,
                    seed=42,
                )

                assert isinstance(result, dict)
                # Should have calculated risk metrics
                assert "risk" in result
                assert "var_95" in result["risk"]
                assert "cvar_95" in result["risk"]
                assert "ruin_prob" in result
                # Should have some ruin probability due to ruinous trade
                assert result["ruin_prob"] > 0

    def test_walk_forward_else_branch_line_200(self):
        """Test walk_forward when run_backtest returns non-tuple line 200."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2, 1.3],
                "high": [1.05, 1.15, 1.25, 1.35],
                "low": [0.95, 1.05, 1.15, 1.25],
                "close": [1.02, 1.12, 1.22, 1.32],
                "volume": [100, 200, 300, 400],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        base_cfg = {
            "initial_cash": 10000.0,
            "user_id": "test",
            "instrument": {"symbol": "EURUSD"},
        }
        strategy_cfg = {"entry_signals": ["long"]}
        grid = {"param1": [1]}

        mock_trade = Mock()
        mock_trade.pnl = 50.0

        with patch("trading_platform.core.sweeps.walk_forward_splits") as mock_splits:
            mock_split = Mock()
            mock_split.train_start = df.index[0]
            mock_split.train_end = df.index[1]
            mock_split.test_start = df.index[2]
            mock_split.test_end = df.index[3]
            mock_splits.return_value = [mock_split]

            with patch(
                "trading_platform.core.sweeps.run_parameter_sweep"
            ) as mock_sweep:
                mock_sweep.return_value = {"top": {"params": {"param1": 1}}}

                with patch(
                    "trading_platform.core.sweeps.compile_strategy"
                ) as mock_compile:
                    mock_strat = Mock()
                    mock_compile.return_value = mock_strat
                    mock_strat.generate_signals.return_value = pd.Series(["long"])

                    with patch(
                        "trading_platform.core.sweeps._run_backtest_simulation"
                    ) as mock_backtest:
                        # Return list directly (not tuple) to test else branch line 200
                        mock_backtest.return_value = [mock_trade]

                        result = walk_forward_optimize_and_test(
                            df=df,
                            base_cfg=base_cfg,
                            strategy_cfg=strategy_cfg,
                            window=2,
                            step=1,
                            grid=grid,
                        )

                        assert isinstance(result, dict)

    def test_monte_carlo_seed_line_286_289(self):
        """Test Monte Carlo seed handling and cost model branches lines 286->289."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Test with None cost_model to trigger getattr default
        mock_cfg = Mock()
        mock_cfg.initial_cash = 10000.0
        # Use getattr to simulate missing cost_model attribute
        del mock_cfg.cost_model  # Remove attribute to test getattr

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        mock_trade.cost_currency = 5.0

        with patch(
            "trading_platform.core.sweeps.RunConfig.model_validate"
        ) as mock_validate:
            mock_validate.return_value = mock_cfg

            with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
                mock_strat = Mock()
                mock_compile.return_value = mock_strat
                mock_strat.generate_signals.return_value = pd.Series(["long"])

                with patch(
                    "trading_platform.core.sweeps._run_backtest_simulation"
                ) as mock_backtest:
                    mock_backtest.return_value = [mock_trade]

                    # Test seeding and cost jitter branches
                    cost_jitter = {"spread_jitter_pct": 0.1}

                    result = monte_carlo_resimulation(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        trials=1,
                        seed=123,  # This should hit line 286
                        cost_jitter=cost_jitter,
                    )

                    assert isinstance(result, dict)

    def test_monte_carlo_cost_jitter_line_302(self):
        """Test Monte Carlo cost jitter model_copy line 302."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        # Create a mock cfg with cost_model
        mock_cfg = Mock()
        mock_cfg.initial_cash = 10000.0
        mock_cfg.cost_model = {"spread_per_unit": 0.001, "slippage_per_unit": 0.001}

        # Create the updated mock for model_copy
        mock_updated_cfg = Mock()
        mock_updated_cfg.initial_cash = 10000.0
        mock_updated_cfg.cost_model = {
            "spread_per_unit": 0.0011,
            "slippage_per_unit": 0.0011,
        }
        mock_cfg.model_copy.return_value = mock_updated_cfg

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        mock_trade.cost_currency = 5.0

        with patch(
            "trading_platform.core.sweeps.RunConfig.model_validate"
        ) as mock_validate:
            mock_validate.return_value = mock_cfg

            with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
                mock_strat = Mock()
                mock_compile.return_value = mock_strat
                mock_strat.generate_signals.return_value = pd.Series(["long"])

                with patch(
                    "trading_platform.core.sweeps._run_backtest_simulation"
                ) as mock_backtest:
                    mock_backtest.return_value = [mock_trade]

                    # Use cost_jitter to trigger line 302
                    cost_jitter = {"spread_jitter_pct": 0.1, "slippage_jitter_pct": 0.1}

                    result = monte_carlo_resimulation(
                        df=df,
                        base_cfg=base_cfg,
                        strategy_cfg=strategy_cfg,
                        trials=1,
                        cost_jitter=cost_jitter,
                    )

                    assert isinstance(result, dict)
                    # Verify model_copy was called (the exact update dict may vary)
                    mock_cfg.model_copy.assert_called_once()

    def test_monte_carlo_tuple_return_line_387(self):
        """Test monte_carlo when run_backtest returns tuple to hit line 387."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2],
                "high": [1.05, 1.15, 1.25],
                "low": [0.95, 1.05, 1.15],
                "close": [1.0, 1.1, 1.2],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        # Mock everything needed for monte_carlo_resimulation
        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps._run_backtest_simulation"
        ) as mock_backtest:
            # Set up mocks
            mock_compile.return_value = Mock()
            # Create a mock trade
            mock_trade = Mock()
            mock_trade.pnl = 100.0

            # Return tuple from run_backtest to hit line 387
            mock_backtest.return_value = ([mock_trade], {"final_equity": 1100.0})

            result = monte_carlo_resimulation(
                df=df,
                base_cfg={"instrument": {"symbol": "EURUSD"}},
                strategy_cfg={"name": "test"},
                trials=1,
                perturbation={"mode": "gaussian", "std_pct": 0.1},
                seed=42,
            )

            assert result is not None

    def test_monte_carlo_empty_equity_vals_edge_cases(self) -> None:
        """Test Monte Carlo edge cases for remaining missing lines."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        base_cfg = {
            "initial_cash": 0.0,
            "instrument": {"symbol": "EURUSD"},
        }  # Zero initial cash to test edge cases
        strategy_cfg = {"entry_signals": ["long"]}

        # Create trades with different outcomes
        zero_trade = Mock()
        zero_trade.pnl = 0.0
        zero_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [zero_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                )

                assert isinstance(result, dict)
                # Test that all metrics are calculated properly even with zero values
                assert "final_equity" in result
                assert "max_drawdown" in result
                assert "win_rate" in result
                assert "time_under_water_mean" in result
                assert "exemplars" in result
                assert "risk" in result
                assert "ruin_prob" in result

    def test_walk_forward_direct_trades_return_line_200(self):
        """Test walk_forward when run_backtest returns trades directly line 200."""
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2, 1.3],
                "high": [1.05, 1.15, 1.25, 1.35],
                "low": [0.95, 1.05, 1.15, 1.25],
                "close": [1.02, 1.12, 1.22, 1.32],
                "volume": [100, 200, 300, 400],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}
        grid = {"param1": [1]}

        mock_trade = Mock()
        mock_trade.pnl = 75.0

        with patch("trading_platform.core.sweeps.walk_forward_splits") as mock_splits:
            mock_split = Mock()
            mock_split.train_start = df.index[0]
            mock_split.train_end = df.index[1]
            mock_split.test_start = df.index[2]
            mock_split.test_end = df.index[3]
            mock_splits.return_value = [mock_split]

            with patch(
                "trading_platform.core.sweeps.run_parameter_sweep"
            ) as mock_sweep:
                mock_sweep.return_value = {"top": {"params": {"param1": 1}}}

                with patch(
                    "trading_platform.core.sweeps.compile_strategy"
                ) as mock_compile:
                    mock_strat = Mock()
                    mock_compile.return_value = mock_strat
                    mock_strat.generate_signals.return_value = pd.Series(["long"])

                    with patch(
                        "trading_platform.core.sweeps._run_backtest_simulation"
                    ) as mock_backtest:
                        # Return trades list (not tuple) to hit else on line 242
                        mock_backtest.return_value = [mock_trade]

                        result = walk_forward_optimize_and_test(
                            df=df,
                            base_cfg=base_cfg,
                            strategy_cfg=strategy_cfg,
                            window=2,
                            step=1,
                            grid=grid,
                        )

                        assert isinstance(result, dict)
                        assert "splits" in result
                        assert len(result["splits"]) == 1
                        assert result["splits"][0]["oos_score"] == 75.0

    def test_monte_carlo_perturbation_std_zero_line_302(self):
        """Test Monte Carlo perturbation with std_pct <= 0 line 302."""
        df = pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]},
            index=pd.date_range("2024-01-01", periods=1, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Perturbation with std_pct = 0 should trigger line 302 return
        perturbation = {"mode": "gaussian", "std_pct": 0.0}

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        mock_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    perturbation=perturbation,
                )

                assert isinstance(result, dict)

    def test_monte_carlo_gaussian_perturbation_basic_coverage(self):
        """Test Monte Carlo Gaussian perturbation basic coverage."""
        df = pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]},
            index=pd.date_range("2024-01-01", periods=1, freq="h"),
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Use perturbation to trigger the float conversion paths
        perturbation = {"mode": "gaussian", "std_pct": 0.01}

        mock_trade = Mock()
        mock_trade.pnl = 100.0
        mock_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [mock_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                    perturbation=perturbation,
                )

                assert isinstance(result, dict)

    def test_monte_carlo_new_peak_and_drawdown_lines_331(self):
        """Test Monte Carlo new peak detection line 331."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {
            "initial_cash": 5000.0,
            "instrument": {"symbol": "EURUSD"},
        }  # Lower initial cash
        strategy_cfg = {"entry_signals": ["long"]}

        # Create a very profitable trade to create new peak
        profitable_trade = Mock()
        profitable_trade.pnl = 7000.0  # Creates new equity peak
        profitable_trade.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = [profitable_trade]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                )

                assert isinstance(result, dict)
                # Final equity should be higher than initial
                assert result["final_equity"]["mean"] > 5000.0

    def test_monte_carlo_basic_empty_trades_lines_387(self):
        """Test Monte Carlo with empty trades - simpler approach line 387."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["flat"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                mock_backtest.return_value = []

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=1,
                )

                assert isinstance(result, dict)
                # With no trades, should still have exemplars
                assert "exemplars" in result

    def test_monte_carlo_var_cvar_calculation_lines_432_442_467(self):
        """Test VaR, CVaR calculations lines 432, 442, 467."""
        df = pd.DataFrame(
            {"close": [1.0]}, index=pd.date_range("2024-01-01", periods=1, freq="h")
        )

        base_cfg = {"initial_cash": 10000.0, "instrument": {"symbol": "EURUSD"}}
        strategy_cfg = {"entry_signals": ["long"]}

        # Create losing trades to trigger CVaR calculation (tail <= var_95)
        losing_trade1 = Mock()
        losing_trade1.pnl = -1000.0
        losing_trade1.cost_currency = 0.0

        losing_trade2 = Mock()
        losing_trade2.pnl = -2000.0
        losing_trade2.cost_currency = 0.0

        losing_trade3 = Mock()
        losing_trade3.pnl = -500.0
        losing_trade3.cost_currency = 0.0

        with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile:
            mock_strat = Mock()
            mock_compile.return_value = mock_strat
            mock_strat.generate_signals.return_value = pd.Series(["long"])

            with patch("trading_platform.core.sweeps._run_backtest_simulation") as mock_backtest:
                # Different outcomes to create distribution for VaR/CVaR
                mock_backtest.side_effect = [
                    [losing_trade1],
                    [losing_trade2],
                    [losing_trade3],
                ]

                result = monte_carlo_resimulation(
                    df=df,
                    base_cfg=base_cfg,
                    strategy_cfg=strategy_cfg,
                    trials=3,
                )

                assert isinstance(result, dict)
                assert "risk" in result
                assert "var_95" in result["risk"]
                assert "cvar_95" in result["risk"]
                # CVaR should be calculated from tail values
                assert result["risk"]["cvar_95"] < 0  # Should be negative for losses


# --- test_sweeps_coverage_gaps.py ---

"""
Test coverage gaps in parameter sweeps module.

Targets specific missing lines in core/sweeps.py to improve coverage.
"""


def test_rmm_context_with_yaml_path():
    """Test _rmm_context with rmm_path pointing to yaml file. Covers lines 22-27."""
    # Create sample market data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )

    # Create a temporary YAML file with RMM config
    rmm_config = {
        "timeframe": "1D",
        "policy": {"min_confidence": 0.7},
        "regimes": [
            {
                "label": "bullish",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 1.0,
                        }
                    ]
                },
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(rmm_config, f)
        yaml_path = f.name

    try:
        cfg_raw = {"rmm_path": yaml_path}

        # Mock the RMMEngine to avoid complex dependencies
        expected_cfg = RMMConfig(**rmm_config)  # type: ignore[arg-type]

        with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            # Mock classify_daily to return simple classification
            mock_daily = pd.DataFrame(
                {"label": ["bullish", "bearish"], "confidence": [0.8, 0.6]},
                index=pd.date_range("2024-01-01", periods=2, freq="D"),
            )
            mock_engine.classify_daily.return_value = mock_daily

            # Mock project_to_index to return projection
            mock_proj = pd.DataFrame(
                {
                    "label": ["bullish", "bearish"],
                    "confidence": [0.8, 0.6],
                    "allowed_sides": [["long"], ["short"]],
                },
                index=df.index,
            )
            mock_engine.project_to_index.return_value = mock_proj

            # Call _rmm_context - this should hit lines 22-27 for YAML loading
            result = _rmm_context(df, cfg_raw)

            # Verify YAML file was loaded and processed
            assert result is not None
            assert len(result) == 2
            mock_engine_class.assert_called_once()
            called_cfg = mock_engine_class.call_args.kwargs["config"]
            assert isinstance(called_cfg, RMMConfig)
            assert called_cfg.model_dump() == expected_cfg.model_dump()

    finally:
        # Clean up temp file
        Path(yaml_path).unlink(missing_ok=True)


def test_rmm_context_with_json_path():
    """Test _rmm_context with rmm_path pointing to json file. Covers lines 22-27."""
    # Create sample market data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )

    # Create a temporary JSON file with RMM config
    rmm_config = {
        "timeframe": "1D",
        "policy": {"min_confidence": 0.7},
        "regimes": [
            {
                "label": "bullish",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 1.0,
                        }
                    ]
                },
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(rmm_config, f)
        json_path = f.name

    try:
        cfg_raw = {"rmm_path": json_path}
        expected_cfg = RMMConfig(**rmm_config)  # type: ignore[arg-type]

        # Mock the RMMEngine to avoid complex dependencies
        with patch("trading_platform.core.sweeps.RMMEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            # Mock classify_daily to return simple classification
            mock_daily = pd.DataFrame(
                {"label": ["bullish", "bearish"], "confidence": [0.8, 0.6]},
                index=pd.date_range("2024-01-01", periods=2, freq="D"),
            )
            mock_engine.classify_daily.return_value = mock_daily

            # Mock project_to_index to return projection
            mock_proj = pd.DataFrame(
                {
                    "label": ["bullish", "bearish"],
                    "confidence": [0.8, 0.6],
                    "allowed_sides": [["long"], ["short"]],
                },
                index=df.index,
            )
            mock_engine.project_to_index.return_value = mock_proj

            # Call _rmm_context - this should hit lines 22-27 for JSON loading
            result = _rmm_context(df, cfg_raw)

            # Verify JSON file was loaded and processed
            assert result is not None
            assert len(result) == 2
            mock_engine_class.assert_called_once()
            called_cfg = mock_engine_class.call_args.kwargs["config"]
            assert isinstance(called_cfg, RMMConfig)
            assert called_cfg.model_dump() == expected_cfg.model_dump()
            assert called_cfg.model_dump() == expected_cfg.model_dump()

    finally:
        # Clean up temp file
        Path(json_path).unlink(missing_ok=True)


def test_rmm_context_empty_config():
    """Test _rmm_context with empty/invalid rmm_config. Covers lines 32-33."""
    df = pd.DataFrame(
        {"close": [1.0, 1.1]}, index=pd.date_range("2024-01-01", periods=2, freq="D")
    )

    # Test with empty dict
    cfg_raw: dict[str, dict[str, str] | str] = {"rmm_config": {}}
    result = _rmm_context(df, cfg_raw)
    assert result is None

    # Test with non-dict rmm_config
    cfg_raw = {"rmm_config": "invalid"}
    result = _rmm_context(df, cfg_raw)
    assert result is None

    # Test with no rmm_config or rmm_path
    cfg_raw = {}
    result = _rmm_context(df, cfg_raw)
    assert result is None


def test_parameter_sweep_with_rem_path():
    """run_parameter_sweep should load REM config when rem_path provided."""
    # Simple market data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    # Create temporary YAML file with REM config
    rem_config = {"daily_loss_cap": 0.02, "position_timeout_hours": 24}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(rem_config, f)
        yaml_path = f.name

    try:
        base_cfg = {
            "user_id": "test_user",
            "run_seed": 42,
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "rem_path": yaml_path,  # This should trigger lines 93-98
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {"entry_signals": ["long"], "exit_signals": ["short"]}

        # Mock dependencies to avoid complex setup
        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps._run_backtest_simulation"
        ) as mock_backtest, patch(
            "trading_platform.core.sweeps.RiskExitManager"
        ) as mock_rem_class:
            mock_compile.return_value = Mock()
            mock_backtest.return_value = ([], [], [])  # trades, exposure, skipped
            mock_rem = Mock()
            mock_rem_class.return_value = mock_rem

            # Simple grid to avoid empty candidates
            grid = {"param1": [1, 2]}

            result = run_parameter_sweep(
                df=df, base_cfg=base_cfg, strategy_cfg=strategy_cfg, grid=grid
            )

            # Verify REM was created with loaded config
            mock_rem_class.assert_called_with(config=rem_config)
            assert isinstance(result, dict)

    finally:
        # Clean up temp file
        Path(yaml_path).unlink(missing_ok=True)


def test_parameter_sweep_with_debug_dir():
    """Test run_parameter_sweep with debug_dir for logging. Covers lines 108-115."""
    # Simple market data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        base_cfg = {
            "user_id": "test_user",
            "run_seed": 42,
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "instrument": {"symbol": "EURUSD"},
        }

        strategy_cfg = {"entry_signals": ["long"], "exit_signals": ["short"]}

        # Mock dependencies to avoid complex setup
        with patch(
            "trading_platform.core.sweeps.compile_strategy"
        ) as mock_compile, patch(
            "trading_platform.core.sweeps._run_backtest_simulation"
        ) as mock_backtest, patch(
            "trading_platform.core.sweeps.RiskExitManager"
        ) as mock_rem_class:
            mock_compile.return_value = Mock()
            mock_backtest.return_value = ([], [], [])  # trades, exposure, skipped
            mock_rem_class.return_value = Mock()

            # Simple grid to avoid empty candidates
            grid = {"param1": [1, 2]}

            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid,
                debug_dir=temp_dir,  # This should trigger lines 108-115
            )

            # Verify debug directory was created and used
            debug_path = Path(temp_dir)
            assert debug_path.exists()
            assert isinstance(result, dict)


def test_parameter_sweep_random_space():
    """Test run_parameter_sweep with random_space sampling. Covers lines 84-86."""
    # Simple market data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 200],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h"),
    )

    base_cfg = {
        "user_id": "test_user",
        "run_seed": 42,
        "initial_cash": 10000.0,
        "position_size": 100.0,
        "instrument": {"symbol": "EURUSD"},
    }

    strategy_cfg = {"entry_signals": ["long"], "exit_signals": ["short"]}

    # Mock dependencies to avoid complex setup
    with patch("trading_platform.core.sweeps.compile_strategy") as mock_compile, patch(
        "trading_platform.core.sweeps._run_backtest_simulation"
    ) as mock_backtest, patch(
        "trading_platform.core.sweeps.RiskExitManager"
    ) as mock_rem_class:
        mock_compile.return_value = Mock()
        mock_backtest.return_value = ([], [], [])  # trades, exposure, skipped
        mock_rem_class.return_value = Mock()

        # Use random_space instead of grid - this should trigger lines 84-86
        random_space = {"param1": [1, 2, 3, 4]}
        n_samples = 2

        result = run_parameter_sweep(
            df=df,
            base_cfg=base_cfg,
            strategy_cfg=strategy_cfg,
            random_space=random_space,
            n_samples=n_samples,
            seed=42,  # For reproducible random sampling
        )

        assert isinstance(result, dict)
        # Should have run exactly n_samples candidates
        assert mock_backtest.call_count == n_samples


# --- test_parameter_sweep_full.py ---


def _df() -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 3, 12)  # 60 hours
    df = create_market_data_with_warmup(
        start_date=start,
        end_date=end,
        freq="1H",
        include_global_features=False,
    )
    # Simple wave to induce a few crosses
    close = [1.0 + 0.001 * ((i % 10) - 5) for i in range(len(df))]
    df["open"] = close
    df["high"] = [c + 0.0005 for c in close]
    df["low"] = [c - 0.0005 for c in close]
    df["close"] = close
    df["volume"] = 1
    return df


def _strategy_cfg() -> dict:
    return {
        "strategy_name": "EMA_Cross_Test",
        "parameters": {
            "ema_fast_length": 3,
            "ema_slow_length": 7,
        },
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": "${ema_fast_length}"},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": "${ema_slow_length}"},
                "source": "close",
            },
        ],
        "overlays": ["ema_fast", "ema_slow"],
        "long_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_above",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "cross_below",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "short_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_below",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "short_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "cross_above",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
    }


def test_run_parameter_sweep_returns_top_and_results():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"type": "offset", "price_offset": 0.002}},
        "instrument": {"symbol": "EURUSD"},
    }
    strat_cfg = _strategy_cfg()
    out = run_parameter_sweep(
        df,
        base_cfg,
        strat_cfg,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        seed=123,
        objective="total_pnl",
    )
    assert "top" in out and "results" in out
    assert len(out["results"]) == 4
    assert set(out["results"][0].keys()) == {"params", "score"}


def test_parameter_sweep_pnl_minus_dd_objective():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"type": "offset", "price_offset": 0.002}},
        "instrument": {"symbol": "EURUSD"},
    }
    strat_cfg = _strategy_cfg()
    out = run_parameter_sweep(
        df,
        base_cfg,
        strat_cfg,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        objective="pnl_minus_dd",
        dd_penalty=0.5,
    )
    assert "top" in out and "results" in out


def test_parameter_sweep_pnl_dd_vol_objective():
    df = _df()
    base_cfg = {
        "initial_cash": 100000.0,
        "position_size": 10000.0,
        "tie_break_policy": {"rule": "stop_then_tp"},
        "rem_config": {"stop_loss": {"type": "offset", "price_offset": 0.002}},
        "instrument": {"symbol": "EURUSD"},
    }
    strat_cfg = _strategy_cfg()
    out = run_parameter_sweep(
        df,
        base_cfg,
        strat_cfg,
        grid={"ema_fast_length": [3, 5], "ema_slow_length": [7, 9]},
        objective="pnl_dd_vol",
        dd_penalty=0.5,
        vol_penalty=0.1,
    )
    assert "top" in out and "results" in out
