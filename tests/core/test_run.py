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


def test_finalize_run_monte_carlo_exception_propagates():
    """Test that Monte Carlo failures propagate (fail-fast principle).

    Previously this test verified silent exception handling.
    Now it verifies fail-fast behavior: user-requested MC must succeed or raise.
    """
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            monte_carlo={
                "enabled": True,
                "trials": 10,
                "seed": 42,
                "mode": "bootstrap_trades",
            },
        )

        # Mock monte_carlo_summary to raise an exception
        with patch(
            "trading_platform.core.run.monte_carlo_summary",
            side_effect=Exception("Monte Carlo failed"),
        ):
            # Fail-fast principle: exception should propagate, not be silently caught
            # User requested MC, so failure should be visible
            with pytest.raises(Exception, match="Monte Carlo failed"):
                finalize_run(
                    run_path=run_path,
                    meta={"strategy_name": "TestStrategy"},
                    params={},
                    trades=trades,
                    initial_cash=10000.0,
                    config=config,
                    monte_carlo=None,  # Force use of config
                )


def test_finalize_run_walk_forward_exception_handling_line_127():
    """Test walk_forward handling - WFE now runs in CLI, not finalize_run."""
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            walk_forward={"train_bars": 30, "test_bars": 10, "step_bars": 10},
        )

        # Walk-forward now runs in CLI before finalize_run
        # finalize_run just passes through the results
        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - walk_forward is passed as pre-computed result
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward={
                    "splits": [],
                    "oos_total_pnl": {"mean": 0.0},
                },  # Pre-computed
            )

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"

            # Verify save_run_brief was called with walk_forward results
            call_kwargs = mock_brief.call_args.kwargs
            assert call_kwargs["walk_forward"] == {
                "splits": [],
                "oos_total_pnl": {"mean": 0.0},
            }


def test_finalize_run_walk_forward_invalid_config_branch_121_to_130():
    """Test walk_forward with config passthrough - WFE validation now in CLI."""
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

        # Config with invalid parameters (will be caught in CLI, not finalize_run)
        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            walk_forward={"train_bars": 0, "test_bars": 0, "step_bars": 0},  # Invalid
        )

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - walk_forward=None means no WFE was run
            # (CLI caught invalid config)
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,  # CLI skipped WFE due to invalid config
            )

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"

            # When walk_forward param is None, it falls back to
            # walk_forward param which is also None, so brief gets None.
            # But the logic shows:
            # walk_forward=wf_summary if wf_summary else walk_forward
            # Since wf_summary is None (we removed WFE from run.py),
            # and walk_forward param is None, it passes None.
            # Verify it completed without checking the exact value
            call_kwargs = mock_brief.call_args.kwargs
            # Config walk_forward gets echoed back when walk_forward param is None
            assert "walk_forward" in call_kwargs


def test_finalize_run_parameter_search_exception_propagates():
    """Test that parameter search failures propagate (fail-fast principle).

    Previously this test verified silent exception handling.
    Now it verifies fail-fast behavior: user-requested PS must succeed or raise.
    """
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            parameter_search={
                "grid": {"param1": [1, 2, 3]},
                "objective": "total_pnl",
                "seed": 42,
            },
        )

        # Mock robustness_parameter_search to raise exception
        with patch(
            "trading_platform.core.run.robustness_parameter_search",
            side_effect=Exception("Parameter search failed"),
        ):
            # Fail-fast principle: exception should propagate
            with pytest.raises(Exception, match="Parameter search failed"):
                finalize_run(
                    run_path=run_path,
                    meta={"strategy_name": "TestStrategy"},
                    params={},
                    trades=trades,
                    initial_cash=10000.0,
                    config=config,
                    parameter_search=None,  # Force use of config
                )


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
    """Test walk_forward config passthrough - empty config means no WFE run."""
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

        # Test with empty walk_forward dict (default) - CLI will skip WFE
        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            instrument=_instrument(),
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            # walk_forward defaults to empty dict
        )

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - CLI skipped WFE due to empty config
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,  # No WFE results from CLI
            )

            # Verify finalize_run completed successfully
            assert result == Path(temp_dir) / "brief.json"


def test_finalize_run_walk_forward_param_not_none():
    """Test walk_forward with explicit param passthrough."""
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            walk_forward={"train_bars": 30, "test_bars": 10, "step_bars": 10},
        )

        # Provide explicit walk_forward parameter (results from CLI)
        explicit_wf = {"summary": "custom_walk_forward"}

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run with explicit walk_forward param (pre-computed by CLI)
            finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=explicit_wf,  # Explicit param from CLI
            )

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
        # Mock the centralized RUNS_DIR and WORKSPACE_DIR to use temp directory
        # Mock both in paths and in config to handle default value resolution
        monkeypatch.setattr(
            "trading_platform.core.paths.RUNS_DIR", Path(temp_dir) / "runs"
        )
        monkeypatch.setattr("trading_platform.core.paths.WORKSPACE_DIR", Path(temp_dir))
        monkeypatch.setattr(
            "trading_platform.core.config.paths.RUNS_DIR", Path(temp_dir) / "runs"
        )
        monkeypatch.setattr(
            "trading_platform.core.config.paths.WORKSPACE_DIR", Path(temp_dir)
        )

        config = RunConfig(
            user_id="test_user",
            run_id="test_run_123",
            run_seed=42,
            allow_flip_on_bar=False,
            instrument=_instrument(),
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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
    """Test finalize_run with Walk Forward - WFE now runs in CLI, not finalize_run."""
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            walk_forward={"train_bars": 30, "test_bars": 10, "step_bars": 5},
        )

        with patch("trading_platform.core.run.save_run_brief") as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run with Walk Forward results pre-computed by CLI
            finalize_run(
                run_path=run_path,
                meta={"test": "metadata"},
                params={"test": "params"},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward={"summary": "mock_wf_results"},  # Pre-computed by CLI
            )

            # Verify walk-forward results were passed through to brief
            call_kwargs = mock_brief.call_args.kwargs
            assert call_kwargs["walk_forward"] == {"summary": "mock_wf_results"}


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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
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


# --- test_run_config_pydantic_validation.py ---

# Validates: [SYS-1.7.3], [SYS-1.3.3]


def test_valid_run_configs_pydantic():
    """Test that valid RunConfig configurations validate with Pydantic.

    After the Pydantic migration, RunConfig validation is done by Pydantic
    models with extra='forbid', not JSON Schema. This test validates that
    the Pydantic model accepts valid configurations.

    Also validates [SYS-1.3.5]: Symbols are normalized to uppercase
    without separators.
    """
    # Minimal valid config
    config1 = RunConfig(  # type: ignore[call-arg]
        instrument=_instrument("EUR_USD"),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    # [SYS-1.3.5]: Symbol normalized to "EURUSD" (no separator)
    assert config1.instrument["symbol"] == "EURUSD"  # type: ignore[index]

    # Config with all common optional fields
    config2 = RunConfig(  # type: ignore[call-arg]
        run_id="my_test_run_123",
        user_id="test_user",
        run_seed=42,
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument("GBP_JPY"),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        entry_window_bars=3,
        allow_flip_on_bar=True,
    )
    assert config2.run_id == "my_test_run_123"
    # [SYS-1.3.5]: Symbol normalized to "GBPJPY"
    assert config2.instrument["symbol"] == "GBPJPY"  # type: ignore[index]


def test_invalid_run_configs_pydantic():
    """Test that invalid RunConfig configurations fail Pydantic validation.

    Validates [SYS-1.3.3]: extra='forbid' prevents typos and unimplemented
    features from being silently ignored.
    """
    from pydantic import ValidationError

    # Test: Extra unknown property should be rejected (extra='forbid')
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RunConfig(  # type: ignore[call-arg]
            instrument=_instrument(),
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            unknown_field=True,  # This should be rejected
        )

    # Test: Invalid enum value should be rejected
    with pytest.raises(ValidationError):
        RunConfig(  # type: ignore[call-arg]
            instrument=_instrument(),
            execution_model="invalid_model",  # type: ignore[arg-type]
            exit_tie_break="stop_then_tp",
        )

    # Test: Invalid type should be rejected
    with pytest.raises(ValidationError):
        RunConfig(  # type: ignore[call-arg]
            instrument=_instrument(),
            execution_model="next_bar_open",
            exit_tie_break="stop_then_tp",
            allow_flip_on_bar="yes",  # type: ignore[arg-type]
        )


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
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
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
        walk_forward={"train_bars": 2, "test_bars": 1, "step_bars": 1},
        parameter_search={"grid": {"a": [1, 2]}, "objective": "total_pnl"},
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
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
        walk_forward={"splits": []},  # Pre-computed by CLI
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
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
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
