"""
Consolidated tests for trading_platform.core.run and its configuration helpers.

Merged from finalize_run and run coverage suites.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest
from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run, initialize_run
from trading_platform.portfolio.trade import Trade
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


# --- test_run_100_coverage.py ---

"""
Comprehensive test coverage for core/run.py to achieve 100% coverage.

This file targets the missing lines and branches identified in the coverage report:
- Line 117: monte_carlo exception handling
- Lines 121->130, 127: walk_forward exception and condition branches
- Line 149: parameter_search exception handling
- Lines 200->215, 212-213: parameter_search CSV export and exception handling
"""


def test_finalize_run_monte_carlo_exception_handling_line_117():
    """Test monte_carlo exception handling to hit line 117."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            monte_carlo={
                "enabled": True,
                "trials": 10,
                "seed": 42,
                "mode": "bootstrap_trades",
            },
        )

        # Mock monte_carlo_summary to raise an exception to hit line 117
        with patch(
            "trading_platform.core.run.monte_carlo_summary",
            side_effect=Exception("Monte Carlo failed"),
        ) as mock_mc, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should handle monte_carlo exception gracefully
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                monte_carlo=None,  # Force use of config
            )

            # Verify monte_carlo_summary was called and failed
            mock_mc.assert_called_once()

            # Verify finalize_run completed successfully despite exception
            assert result == Path(temp_dir) / "brief.json"

            # Verify save_run_brief was called with config monte_carlo
            # When mc_summary is None due to exception, it falls back to
            # monte_carlo param which gets set to config.monte_carlo
            call_kwargs = mock_brief.call_args.kwargs
            expected_mc = {
                "enabled": True,
                "trials": 10,
                "seed": 42,
                "mode": "bootstrap_trades",
            }
            assert call_kwargs["monte_carlo"] == expected_mc


def test_finalize_run_walk_forward_exception_handling_line_127():
    """Test walk_forward exception handling to hit line 127."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            walk_forward={"window": 30, "step": 10},
        )

        # Mock walk_forward_summary to raise an exception to hit line 127
        with patch(
            "trading_platform.core.run.walk_forward_summary",
            side_effect=Exception("Walk Forward failed"),
        ) as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should handle walk_forward exception gracefully
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,  # Force use of config
            )

            # Verify walk_forward_summary was called and failed
            mock_wf.assert_called_once()

            # Verify finalize_run completed successfully despite exception
            assert result == Path(temp_dir) / "brief.json"

            # Verify save_run_brief was called with config walk_forward
            # When wf_summary is None due to exception, it falls back to
            # walk_forward param which gets set to config.walk_forward
            call_kwargs = mock_brief.call_args.kwargs
            expected_wf = {"window": 30, "step": 10}
            assert call_kwargs["walk_forward"] == expected_wf


def test_finalize_run_walk_forward_invalid_config_branch_121_to_130():
    """Test walk_forward with invalid config to hit branch 121->130."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        # Test with window=0, step=0 to skip walk_forward analysis
        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            walk_forward={"window": 0, "step": 0},  # Invalid config
        )

        with patch("trading_platform.core.run.walk_forward_summary") as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should skip walk_forward due to invalid config
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,  # Force use of config
            )

            # Verify walk_forward_summary was NOT called due to invalid config
            mock_wf.assert_not_called()

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"

            # Verify save_run_brief was called with walk_forward config (not summary)
            call_kwargs = mock_brief.call_args.kwargs
            assert call_kwargs["walk_forward"] == {"window": 0, "step": 0}


def test_finalize_run_parameter_search_exception_handling_line_149():
    """Test parameter_search exception handling to hit line 149."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            parameter_search={
                "grid": {"param1": [1, 2, 3]},
                "objective": "total_pnl",
                "seed": 42,
            },
        )

        # Mock robustness_parameter_search to raise exception to hit line 149
        with patch(
            "trading_platform.core.run.robustness_parameter_search",
            side_effect=Exception("Parameter search failed"),
        ) as mock_ps, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should handle parameter_search exception gracefully
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                parameter_search=None,  # Force use of config
            )

            # Verify robustness_parameter_search was called and failed
            mock_ps.assert_called_once()

            # Verify finalize_run completed successfully despite exception
            assert result == Path(temp_dir) / "brief.json"

            # Verify save_run_brief was called with parameter_search config
            call_kwargs = mock_brief.call_args.kwargs
            assert call_kwargs["parameter_search"] == config.parameter_search


def test_finalize_run_parameter_search_csv_export_lines_212_213():
    """Test parameter_search CSV export to hit lines 212-213."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        # Create parameter_search results with mixed parameter keys to test CSV logic
        parameter_search_payload = {
            "results": [
                {"params": {"param1": 1, "param2": "A"}, "score": 0.85},
                {"params": {"param1": 2, "param3": "B"}, "score": 0.92},  # diff params
                {
                    "params": {"param2": "C", "param4": 100},
                    "score": 0.78,
                },  # diff params
            ]
        }

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run with parameter_search results
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                parameter_search=parameter_search_payload,
            )

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"

            # Verify CSV file was created (lines 212-213)
            csv_path = run_path / "parameter_search_results.csv"
            assert csv_path.exists()

            # Read and verify CSV content
            content = csv_path.read_text()
            lines = content.strip().split("\n")

            # Should have header + 3 data rows
            assert len(lines) == 4

            # Check that all parameter keys are in header (stable key collection)
            header = lines[0]
            assert "param1" in header
            assert "param2" in header
            assert "param3" in header
            assert "param4" in header
            assert "score" in header

            # Verify score values are present
            assert "0.85" in content
            assert "0.92" in content
            assert "0.78" in content


def test_finalize_run_parameter_search_csv_export_exception_branch_200_to_215():
    """Test parameter_search CSV export exception handling to hit branch 200->215."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        # Create parameter_search results that will cause CSV writing to fail
        parameter_search_payload = {
            "results": [
                {"params": {"param1": 1}, "score": 0.85},
            ]
        }

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ), patch("csv.DictWriter.writerows", side_effect=Exception("CSV write failed")):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should handle CSV exception gracefully
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                parameter_search=parameter_search_payload,
            )

            # Verify finalize_run completed successfully despite CSV exception
            assert result == Path(temp_dir) / "brief.json"


def test_finalize_run_parameter_search_no_results():
    """Test parameter_search with no results to skip CSV export."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        # Create parameter_search results without results list
        parameter_search_payload = {"summary": "No results"}

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                parameter_search=parameter_search_payload,
            )

            # Verify CSV file was NOT created (no results)
            csv_path = run_path / "parameter_search_results.csv"
            assert not csv_path.exists()

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"


def test_finalize_run_empty_parameter_search_results():
    """Test parameter_search with empty results list to skip CSV export."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        # Create parameter_search results with empty results list
        parameter_search_payload: dict[str, Any] = {"results": []}

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                parameter_search=parameter_search_payload,
            )

            # Verify CSV file was NOT created (empty results)
            csv_path = run_path / "parameter_search_results.csv"
            assert not csv_path.exists()

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"


def test_finalize_run_walk_forward_non_dict_config():
    """Test walk_forward config behavior in different scenarios."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        # Test with empty walk_forward dict (default) to skip analysis
        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            # walk_forward defaults to empty dict, causing isinstance check to pass
            # but skip analysis due to missing required keys
        )

        with patch("trading_platform.core.run.walk_forward_summary") as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should skip walk_forward analysis
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,  # Force use of config
            )

            # Verify walk_forward_summary was NOT called due to empty walk_forward
            # config
            mock_wf.assert_not_called()

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"


def test_finalize_run_walk_forward_param_not_none():
    """Test walk_forward with explicit param to miss branch 121->130."""
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
            exit_reason="signal",
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        run_path = Path(temp_dir)

        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            walk_forward={"window": 30, "step": 10},
        )

        # Provide explicit walk_forward parameter to bypass config processing
        explicit_wf = {"summary": "custom_walk_forward"}

        with patch("trading_platform.core.run.walk_forward_summary") as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run with explicit walk_forward param
            finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=explicit_wf,  # Explicit param, skips config processing
            )

            # Verify walk_forward_summary was NOT called due to explicit param
            mock_wf.assert_not_called()

            # Verify save_run_brief was called with explicit walk_forward param
            call_kwargs = mock_brief.call_args.kwargs
            assert call_kwargs["walk_forward"] == explicit_wf


# --- test_run_coverage_gaps.py ---

"""
Test coverage gaps in core run module.

Targets specific missing lines in core/run.py to improve coverage.
"""


def test_initialize_run_creates_directory_and_config(monkeypatch):
    """Test initialize_run function. Covers lines 27-32."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the centralized RUNS_DIR to use our temp directory
        monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", Path(temp_dir) / "runs")

        config = RunConfig(
            user_id="test_user",
            run_id="test_run_123",
            run_seed=42,
            allow_flip_on_bar=False,
            instrument=_instrument(),
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            monte_carlo={
                "enabled": True,
                "trials": 50,
                "seed": 42,
                "mode": "bootstrap_trades",
            },
        )

        with patch("trading_platform.core.run.monte_carlo_summary") as mock_mc, patch(
            "trading_platform.core.run.save_run_brief"
        ), patch("trading_platform.core.run.save_chart_from_brief"), patch(
            "trading_platform.core.run.save_trades_csv"
        ), patch("trading_platform.core.run.save_html_report"):
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
            )

            # Verify Monte Carlo summary was called with correct parameters
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            walk_forward={"window": 30, "step": 5},
        )

        with patch("trading_platform.core.run.walk_forward_summary") as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ), patch("trading_platform.core.run.save_chart_from_brief"), patch(
            "trading_platform.core.run.save_trades_csv"
        ), patch("trading_platform.core.run.save_html_report"):
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            parameter_search={
                "grid": {"param1": [1, 2, 3]},
                "objective": "total_pnl",
                "seed": 42,
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

            # Verify Parameter Search was called
            mock_ps.assert_called_once()
            call_kwargs = mock_ps.call_args.kwargs
            assert call_kwargs["grid"] == {"param1": [1, 2, 3]}
            assert call_kwargs["seed"] == 42

            # Verify evaluate function works correctly
            eval_fn = call_kwargs["evaluate"]
            assert eval_fn({}) == 70.0  # sum of pnl from both trades (50 + 20)


def test_finalize_run_parameter_search_random_space():
    """Random-space parameter search should respect config seed and space."""
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
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
    """CSV export errors should be swallowed and logged."""
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
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
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


# --- test_run_config_schema.py ---

# Validates: [SYS-1.7.3]

SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "docs/schemas/run_config.schema.json"
)


@pytest.fixture(scope="module")
def run_config_schema():
    """Loads the RunConfig JSON schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_schema_is_valid_json(run_config_schema):
    """Ensure the schema itself is a valid JSON document."""
    assert isinstance(run_config_schema, dict)


def test_valid_run_configs(run_config_schema):
    """Test that valid RunConfig configurations validate successfully."""
    valid_configs = [
        # Minimal required config
        {
            "strategy": "config/strategy/ema_crossover.yaml",
            "instrument": {"symbol": "EUR_USD", "timeframe": "H1"},
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
        # Config with all optional components
        {
            "run_id": "my_test_run_123",
            "strategy": "config/strategy/ema_crossover.yaml",
            "rem": "config/rem/basic_price_exits.yaml",
            "rmm": "config/rmm/daily_trend.yaml",
            "instrument": {"symbol": "GBP_JPY", "timeframe": "D1"},
            "data": {
                "source": "oanda",
                "start_date": "2020-01-01",
                "end_date": "2024-01-01",
            },
        },
    ]

    for config in valid_configs:
        try:
            jsonschema.validate(instance=config, schema=run_config_schema)
        except jsonschema.ValidationError as e:
            pytest.fail(f"Valid config failed validation: {config}\n{e}")


def test_invalid_run_configs(run_config_schema):
    """Test that invalid RunConfig configurations fail validation."""
    invalid_configs = [
        # Missing required 'instrument'
        {
            "strategy": "config/strategy/ema_crossover.yaml",
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
        # Missing required 'strategy'
        {
            "instrument": {"symbol": "EUR_USD", "timeframe": "H1"},
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
        # Extra unknown property
        {
            "strategy": "config/strategy/ema_crossover.yaml",
            "instrument": {"symbol": "EUR_USD", "timeframe": "H1"},
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
            "unknown_field": True,
        },
    ]

    for config in invalid_configs:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=config, schema=run_config_schema)


# --- test_finalize_run.py ---

# Validates: [RV-9.1], [SYS-1.7.1]


def _simple_trade(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="T",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_finalize_run_writes_brief(tmp_path):
    run_path = tmp_path / "user" / "runA"
    trades = [_simple_trade(datetime(2023, 1, 1, 0), 10.0)]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "runA"},
        params={},
        trades=trades,
        initial_cash=1000.0,
    )
    assert brief_path.exists()


def test_finalize_run_model_analysis(tmp_path):
    run_path = tmp_path / "user" / "runB"
    # One TP, one SL, one normal trade
    from datetime import datetime

    from trading_platform.portfolio.trade import Trade

    trades = [
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 1, 0),
            exit_time=datetime(2023, 1, 1, 1),
            entry_price=1.0,
            exit_price=1.2,
            side="long",
            size=1.0,
            pnl=0.2,
            exit_reason="take_profit",
            mfe_currency=0.5,
            mae_currency=0.1,
        ),
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 2, 0),
            exit_time=datetime(2023, 1, 2, 1),
            entry_price=1.0,
            exit_price=0.8,
            side="long",
            size=1.0,
            pnl=-0.2,
            exit_reason="stop_loss",
            mfe_currency=0.1,
            mae_currency=0.4,
        ),
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 3, 0),
            exit_time=datetime(2023, 1, 3, 1),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=1.0,
            pnl=0.1,
            exit_reason="signal",
            mfe_currency=0.2,
            mae_currency=0.05,
        ),
    ]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "runB"},
        params={},
        trades=trades,
        initial_cash=1000.0,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert "model_analysis" in data
    ma = data["model_analysis"]
    assert "avg_pnl_left_on_table_at_tp" in ma
    assert "avg_loss_avoided_by_stop" in ma
    # Check values are as expected
    assert abs(ma["avg_pnl_left_on_table_at_tp"] - (0.5 - 0.2)) < 1e-8
    assert abs(ma["avg_loss_avoided_by_stop"] - (0.4 - 0.2)) < 1e-8


def test_finalize_run_signal_quality_analysis(tmp_path):
    import pandas as pd
    from trading_platform.core.run import finalize_run

    # Create a mock signals.parquet file
    run_path = tmp_path / "user" / "runC"
    run_path.mkdir(parents=True, exist_ok=True)
    signals_path = run_path / "signals.parquet"
    # Simulate a command signal series: 14 bars with 5 commands total
    sigs = pd.Series(
        [
            "enter_long",
            None,
            None,
            "exit_long",
            None,
            "enter_short",
            "exit_short",
            None,
            None,
            None,
            "enter_long",
            None,
            None,
            "exit_long",
        ],
        name="signal",
    )
    sigs.to_frame().to_parquet(signals_path)
    # Minimal trades list
    from datetime import datetime

    from trading_platform.portfolio.trade import Trade

    trades = [
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 1, 0),
            exit_time=datetime(2023, 1, 1, 1),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=1.0,
            pnl=0.1,
            exit_reason="signal",
        ),
    ]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "runC"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        signals_path=signals_path,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert "signal_quality_analysis" in data
    sqa = data["signal_quality_analysis"]
    assert "signal_persistence_pct" in sqa
    assert "avg_signal_duration_bars" in sqa
    # There are 6 non-None commands out of 14 total
    assert abs(sqa["signal_persistence_pct"] - (6 / 14 * 100)) < 1e-2
    # Commands fire once, so avg duration = 1.0
    assert abs(sqa["avg_signal_duration_bars"] - 1.0) < 1e-6


# --- test_finalize_run_config_injection.py ---

# Validates: [JSON-11.18], [JSON-11.19], [JSON-11.20]


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        parameters={},
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
    )


def _t(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="EUR_USD",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=pnl,
    )


def test_finalize_run_uses_config_snapshots(tmp_path):
    run_path = tmp_path / "user" / "run123"
    cfg = RunConfig(
        user_id="user",
        run_id="run123",
        runs_dir=tmp_path,
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        instrument_definitions={
            "EURUSD": {"symbol": "EURUSD", "tick_size": 0.0001, "base_ccy": "EUR"}
        },
        cost_model={"type": "none"},
        fill_policy={"policy": "market"},
        tie_break_policy={"rule": "stop_then_tp"},
    )

    out_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "run123"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 10.0)],
        initial_cash=1000.0,
        config=cfg,
    )

    data = json.loads(out_path.read_text())
    assert data["instrument_definitions"]["EURUSD"]["tick_size"] == 0.0001
    assert data["cost_model"]["type"] == "none"
    assert data["fill_policy"]["policy"] == "market"
    assert data["tie_break_policy"]["rule"] == "stop_then_tp"


# --- test_finalize_run_mc_wfe_paramsearch.py ---

# Validates: [JSON-F.1], [JSON-F.2], [JSON-F.3]


def _dummy_strategy_2() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        parameters={},
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
    )


def _t2(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
    )


def test_finalize_run_populates_mc_wfe_paramsearch(tmp_path):
    run_path = tmp_path / "u" / "r"
    cfg = RunConfig(
        user_id="u",
        run_id="r",
        runs_dir=tmp_path,
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        monte_carlo={"trials": 50, "seed": 123},
        walk_forward={"window": 2, "step": 1},
        parameter_search={"grid": {"a": [1, 2]}, "objective": "total_pnl"},
    )
    out = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[
            _t2(datetime(2024, 1, 1), 5.0),
            _t2(datetime(2024, 1, 1, 1), -5.0),
            _t2(datetime(2024, 1, 1, 2), 10.0),
        ],
        initial_cash=1000.0,
        config=cfg,
    )
    data = out.read_text()
    assert '"monte_carlo"' in data and '"walk_forward"' in data
    assert '"parameter_search"' in data


# --- test_finalize_run_prefer_args.py ---


def _t3(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long",
        size=1.0,
        pnl=pnl,
    )


def test_finalize_run_prefers_explicit_mc_over_config(tmp_path):
    run_path = tmp_path / "u" / "r"
    cfg = RunConfig(
        user_id="u",
        run_id="r",
        runs_dir=tmp_path,
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        monte_carlo={"trials": 1},
    )
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[_t3(datetime(2024, 1, 1), 1.0)],
        initial_cash=1000.0,
        config=cfg,
        monte_carlo={"mode": "test", "trials": 1},
    )
    data = brief_path.read_text()
    assert '"mode": "test"' in data


# --- test_finalize_run_regimes.py ---


def _trade(ts: datetime, pnl: float, regime: str) -> Trade:
    return Trade(
        symbol="T",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_finalize_run_regimes_section(tmp_path):
    run_path = tmp_path / "user" / "run_regimes"
    # Simulate 3 trades in 2 regimes
    trades = [
        _trade(datetime(2023, 1, 1, 0), 10.0, "bull"),
        _trade(datetime(2023, 1, 2, 0), -5.0, "bear"),
        _trade(datetime(2023, 1, 3, 0), 20.0, "bull"),
    ]
    regimes_at_entry = ["bull", "bear", "bull"]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "run_regimes"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        regimes_at_entry=regimes_at_entry,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert "regimes" in data
    regimes = data["regimes"]
    assert set(regimes.keys()) == {"bull", "bear"}
    # Check bull regime
    bull = regimes["bull"]
    assert bull["n_trades"] == 2
    assert bull["total_pnl"] == 30.0
    assert bull["mean_pnl"] == 15.0
    assert bull["median_pnl"] == 15.0
    assert bull["win_rate"] == 1.0
    # Check bear regime
    bear = regimes["bear"]
    assert bear["n_trades"] == 1
    assert bear["total_pnl"] == -5.0
    assert bear["mean_pnl"] == -5.0
    assert bear["median_pnl"] == -5.0
    assert bear["win_rate"] == 0.0
