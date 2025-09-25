"""
Test coverage gaps in core run module.

Targets specific missing lines in core/run.py to improve coverage.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run, initialize_run
from trading_platform.portfolio.trade import Trade


def test_initialize_run_creates_directory_and_config():
    """Test initialize_run function. Covers lines 27-32."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = RunConfig(
            user_id="test_user",
            run_id="test_run_123",
            runs_dir=Path(temp_dir) / "runs",
            log_level="INFO",
            initial_cash=10000.0,
            position_size=100.0,
        )

        # Call initialize_run - should create directory and save config
        with patch("logging.info") as mock_log:
            run_path = initialize_run(config)

            # Verify directory structure
            expected_path = Path(temp_dir) / "runs" / "test_user" / "test_run_123"
            assert run_path == expected_path
            assert run_path.exists()

            # Verify config.json was created
            config_path = run_path / "config.json"
            assert config_path.exists()

            # Verify logging was called
            mock_log.assert_called_once()
            assert "Initialized run artifacts" in mock_log.call_args[0][0]


def test_finalize_run_monte_carlo_enabled():
    """Test finalize_run with Monte Carlo analysis enabled. Covers lines 103-110."""
    # Create sample trades
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            monte_carlo={
                "enabled": True,
                "trials": 50,
                "seed": 42,
                "mode": "bootstrap_trades",
            },
        )

        with patch("trading_platform.core.run.monte_carlo_summary") as mock_mc, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ) as mock_chart, patch(
            "trading_platform.core.run.save_trades_csv"
        ) as mock_csv, patch("trading_platform.core.run.save_html_report") as mock_html:
            mock_mc.return_value = {"summary": "mock_mc_results"}

            # Call finalize_run with Monte Carlo enabled (via config)
            # Explicitly pass monte_carlo=None to trigger analysis from config
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                monte_carlo=None,
            )  # Verify Monte Carlo summary was called with correct parameters
            mock_mc.assert_called_once_with(
                trades,
                initial_cash=10000.0,
                trials=100,  # max(50, 100) = 100
                seed=42,
                mode="bootstrap_trades",
            )


def test_finalize_run_walk_forward_enabled():
    """Test finalize_run with Walk Forward analysis enabled. Covers lines 119-120."""
    # Create sample trades
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            walk_forward={"window": 30, "step": 5},
        )

        with patch("trading_platform.core.run.walk_forward_summary") as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ) as mock_chart, patch(
            "trading_platform.core.run.save_trades_csv"
        ) as mock_csv, patch("trading_platform.core.run.save_html_report") as mock_html:
            mock_wf.return_value = {"summary": "mock_wf_results"}

            # Call finalize_run with Walk Forward enabled (via config)
            # Explicitly pass walk_forward=None to trigger analysis from config
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,
            )

            # Verify Walk Forward summary was called with correct parameters
            mock_wf.assert_called_once_with(trades, window=30, step=5)


def test_finalize_run_parameter_search_enabled():
    """Test finalize_run with Parameter Search enabled. Covers lines 124->147."""
    # Create sample trades
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 11, 0),
            exit_time=datetime(2024, 1, 1, 12, 0),
            side="short",
            size=100.0,
            entry_price=1.1040,
            exit_price=1.1020,
            pnl=20.0,
        ),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            parameter_search={
                "grid": {"param1": [1, 2, 3]},
                "objective": "total_pnl",
                "seed": 42,
            },
        )

        with patch(
            "trading_platform.core.run.robustness_parameter_search"
        ) as mock_ps, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ) as mock_chart, patch(
            "trading_platform.core.run.save_trades_csv"
        ) as mock_csv, patch("trading_platform.core.run.save_html_report") as mock_html:
            mock_ps.return_value = {"summary": "mock_ps_results"}

            # Call finalize_run with Parameter Search enabled (via config)
            # Explicitly pass parameter_search=None to trigger analysis from config
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                parameter_search=None,
            )

            # Verify Parameter Search was called
            mock_ps.assert_called_once()
            call_kwargs = mock_ps.call_args.kwargs
            assert call_kwargs["grid"] == {"param1": [1, 2, 3]}
            assert call_kwargs["seed"] == 42

            # Verify evaluate function works correctly
            eval_fn = call_kwargs["evaluate"]
            assert eval_fn({}) == 70.0  # sum of pnl from both trades (50 + 20)


def test_finalize_run_parameter_search_random_space():
    """Test finalize_run with Parameter Search using random_space. Covers lines 124->147."""
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            parameter_search={
                "random_space": {"param1": [1.0, 2.0, 3.0]},
                "n_samples": 10,
                "objective": "total_pnl",
            },
        )

        with patch(
            "trading_platform.core.run.robustness_parameter_search"
        ) as mock_ps, patch("trading_platform.core.run.save_run_brief"), patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_ps.return_value = {"summary": "mock_ps_results"}

            # Call finalize_run with Parameter Search enabled (via config)
            # Explicitly pass parameter_search=None to trigger analysis from config
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                parameter_search=None,
            )

            # Verify Parameter Search was called with random_space
            mock_ps.assert_called_once()
            call_kwargs = mock_ps.call_args.kwargs
            assert call_kwargs["random_space"] == {"param1": [1.0, 2.0, 3.0]}
            assert call_kwargs["n_samples"] == 10


def test_finalize_run_parameter_search_export_csv():
    """Test finalize_run exports parameter search results CSV. Covers lines 185-206."""
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
        )

        # Mock parameter search results with detailed structure
        parameter_search_payload = {
            "results": [
                {"params": {"param1": 1, "param2": "value1"}, "score": 0.85},
                {"params": {"param1": 2, "param2": "value2"}, "score": 0.92},
                {"params": {"param1": 3}, "score": 0.78},  # Missing param2
            ]
        }

        with patch("trading_platform.core.run.save_run_brief"), patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            # Call finalize_run with parameter search payload
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                parameter_search=parameter_search_payload,
            )

            # Verify CSV file was created
            csv_path = run_path / "parameter_search_results.csv"
            assert csv_path.exists()

            # Verify CSV content
            content = csv_path.read_text()
            assert "param1" in content
            assert "param2" in content
            assert "score" in content
            assert "0.85" in content
            assert "0.92" in content
            assert "value1" in content


def test_finalize_run_exception_handling():
    """Test finalize_run handles exceptions gracefully. Covers exception branches."""
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
        )

        # Test Monte Carlo exception handling
        monte_carlo_cfg = {"enabled": True, "trials": 10}

        with patch(
            "trading_platform.core.run.monte_carlo_summary",
            side_effect=Exception("MC Error"),
        ), patch("trading_platform.core.run.save_run_brief"), patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            # Should not raise exception, should handle gracefully
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                monte_carlo=monte_carlo_cfg,
            )

            # Test should complete successfully despite Monte Carlo exception


def test_finalize_run_parameter_search_csv_export_exception():
    """Test parameter search CSV export handles exceptions. Covers exception in lines 185-206."""
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
        )

        # Create malformed parameter search payload to trigger exception
        parameter_search_payload = {
            "results": [
                {
                    "params": {"param1": 1},
                    "score": float("inf"),
                },  # Invalid float for CSV
            ]
        }

        with patch("trading_platform.core.run.save_run_brief"), patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            # Should handle CSV export exception gracefully
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                parameter_search=parameter_search_payload,
            )

            # Test should complete successfully despite CSV export exception
