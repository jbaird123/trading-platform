"""
Comprehensive test coverage for core/run.py to achieve 100% coverage.

This file targets the missing lines and branches identified in the coverage report:
- Line 117: monte_carlo exception handling
- Lines 121->130, 127: walk_forward exception and condition branches
- Line 149: parameter_search exception handling
- Lines 200->215, 212-213: parameter_search CSV export and exception handling
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade


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
        parameter_search_payload: Dict[str, Any] = {"results": []}

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
    """Test walk_forward with non-dict config to skip analysis."""
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

        # Test with non-dict walk_forward config
        config = RunConfig(
            user_id="test_user",
            initial_cash=10000.0,
            position_size=100.0,
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
        )
        # Manually set walk_forward to non-dict to test isinstance check
        config.walk_forward = "invalid_config"  # type: ignore

        with patch("trading_platform.core.run.walk_forward_summary") as mock_wf, patch(
            "trading_platform.core.run.save_run_brief"
        ) as mock_brief, patch(
            "trading_platform.core.run.save_chart_from_brief"
        ), patch("trading_platform.core.run.save_trades_csv"), patch(
            "trading_platform.core.run.save_html_report"
        ):
            mock_brief.return_value = Path(temp_dir) / "brief.json"

            # Call finalize_run - should skip walk_forward due to non-dict config
            result = finalize_run(
                run_path=run_path,
                meta={"strategy_name": "TestStrategy"},
                params={},
                trades=trades,
                initial_cash=10000.0,
                config=config,
                walk_forward=None,  # Force use of config
            )

            # Verify walk_forward_summary was NOT called due to non-dict config
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
