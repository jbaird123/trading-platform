"""Final tests to reach maximum CLI coverage - only working tests."""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd


class TestParamsSnapshotBranches:
    """Test params_snapshot branches (lines 377-379)."""

    def test_params_from_strategy_defaults(self, tmp_path: Path) -> None:
        """Test elif branch: no strategy_params, use strategy parameters
        (line 377-378)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_params_defaults",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            # NO strategy_params, so it should use strategy.parameters
            "strategy": {
                "strategy_name": "Test",
                "parameters": {
                    "my_param": 42
                },  # This should be used for params_snapshot
                "long_entry_rules": [
                    {
                        "any_of": [
                            {"condition": "is_above", "left": "close", "right": 1.0}
                        ]
                    }
                ],
                "long_exit_rules": [
                    {
                        "any_of": [
                            {"condition": "is_below", "left": "close", "right": 1.0}
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
            mock_backtest.return_value = {
                "trades": [],
                "equity_curve": [],
                "strategy_name": "Test",
                "initial_capital": 100000,
                "compiled_strategy": mock_strat,
                "feature_enriched_df": pd.DataFrame(),
            }

            result = cmd_run_backtest(args)
            assert result == 0


class TestDataQualityFlagsBranch:
    """Test dq_flags branch (line 381)."""

    def test_with_dq_flags_from_loader(self, tmp_path: Path) -> None:
        """Test when load_instrument_data returns flags (line 381)."""
        from trading_platform.cli import cmd_run_backtest

        config_path = tmp_path / "config.json"
        config = {
            "run_id": "test_dq_flags",
            "instrument": {"symbol": "EURUSD"},
            "initial_cash": 100000,
            "data_request": {
                "symbol": "EURUSD",
                "timeframe": "1H",
            },
            "strategy": {
                "strategy_name": "Test",
                "long_entry_rules": [
                    {
                        "any_of": [
                            {"condition": "is_above", "left": "close", "right": 1.0}
                        ]
                    }
                ],
                "long_exit_rules": [
                    {
                        "any_of": [
                            {"condition": "is_below", "left": "close", "right": 1.0}
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

            # Return data with flags
            dq_flags = ["missing_data", "price_spike"]
            mock_load.return_value = (df, dq_flags)

            mock_strat = MagicMock()
            mock_strat._feature_df = pd.DataFrame()
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {
                "trades": [],
                "equity_curve": [],
                "strategy_name": "Test",
                "initial_capital": 100000,
                "compiled_strategy": mock_strat,
                "feature_enriched_df": pd.DataFrame(),
            }

            result = cmd_run_backtest(args)
            assert result == 0


class TestCmdCompareLastFlag:
    """Test cmd_compare with --last flag (lines 593-614)."""

    def test_compare_last_with_2_briefs(self, tmp_path: Path) -> None:
        """Test cmd_compare --last 2 creates comparison."""
        from trading_platform.cli import cmd_compare

        # Create runs directory with 2 briefs
        runs_base = tmp_path / "runs"
        runs_base.mkdir()
        user_dir = runs_base / "testuser"
        user_dir.mkdir()

        brief1 = user_dir / "run1" / "brief.json"
        brief1.parent.mkdir()
        brief2 = user_dir / "run2" / "brief.json"
        brief2.parent.mkdir()

        brief_data1 = {
            "meta": {"run_id": "run1"},
            "backtest": {
                "trades": [],
                "metrics": {"total_pnl": 100},
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief_data2 = {
            "meta": {"run_id": "run2"},
            "backtest": {
                "trades": [],
                "metrics": {"total_pnl": 200},
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }

        brief1.write_text(json.dumps(brief_data1))
        brief2.write_text(json.dumps(brief_data2))

        args = argparse.Namespace(
            last=2, a=None, b=None, out=None, runs_dir=str(runs_base), user="testuser"
        )

        with patch("trading_platform.cli.save_comparison_report") as mock_save:
            result = cmd_compare(args)

            assert result == 0
            assert mock_save.call_count == 1

    def test_compare_last_insufficient_briefs(self, tmp_path: Path) -> None:
        """Test cmd_compare --last when not enough briefs found (lines 596-598)."""
        from trading_platform.cli import cmd_compare

        runs_base = tmp_path / "runs"
        runs_base.mkdir()
        user_dir = runs_base / "testuser"
        user_dir.mkdir()

        # Only create 1 brief when 2 requested
        brief1 = user_dir / "run1" / "brief.json"
        brief1.parent.mkdir()
        brief_data = {
            "meta": {"run_id": "run1"},
            "backtest": {
                "trades": [],
                "metrics": {"total_pnl": 100},
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief1.write_text(json.dumps(brief_data))

        args = argparse.Namespace(
            last=2, a=None, b=None, out=None, runs_dir=str(runs_base), user="testuser"
        )

        result = cmd_compare(args)
        assert result == 2  # Should fail


class TestCmdOpenChartWithOpen:
    """Test cmd_open_chart with --open flag (lines 645-650)."""

    def test_open_chart_with_open_flag(self, tmp_path: Path) -> None:
        """Test opening chart in browser."""
        from trading_platform.cli import cmd_open_chart

        # Create runs directory with brief and chart
        runs_base = tmp_path / "runs"
        runs_base.mkdir()
        user_dir = runs_base / "testuser"
        user_dir.mkdir()

        run1_dir = user_dir / "run1"
        run1_dir.mkdir()
        brief = run1_dir / "brief.json"
        chart = run1_dir / "chart.html"

        brief_data = {
            "backtest": {
                "run_id": "run1",
                "trades": [],
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief.write_text(json.dumps(brief_data))
        chart.write_text("<html></html>")

        args = argparse.Namespace(
            runs_dir=str(runs_base), user="testuser", last=1, open=True
        )

        with patch("webbrowser.open") as mock_browser:
            result = cmd_open_chart(args)

            assert result == 0
            assert mock_browser.call_count == 1

    def test_open_chart_browser_fails(self, tmp_path: Path) -> None:
        """Test that browser failure doesn't crash (line 649-650)."""
        from trading_platform.cli import cmd_open_chart

        runs_base = tmp_path / "runs"
        runs_base.mkdir()
        user_dir = runs_base / "testuser"
        user_dir.mkdir()

        run1_dir = user_dir / "run1"
        run1_dir.mkdir()
        brief = run1_dir / "brief.json"
        chart = run1_dir / "chart.html"

        brief_data = {
            "backtest": {
                "run_id": "run1",
                "trades": [],
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief.write_text(json.dumps(brief_data))
        chart.write_text("<html></html>")

        args = argparse.Namespace(
            runs_dir=str(runs_base), user="testuser", last=1, open=True
        )

        with patch("webbrowser.open", side_effect=Exception("Browser error")):
            result = cmd_open_chart(args)
            # Should still succeed despite browser failure
            assert result == 0


class TestAIDiagnoseQualitativeReport:
    """Test cmd_ai_diagnose with qualitative_report_path (lines 501-509)."""

    def test_with_qualitative_report_path(self, tmp_path: Path) -> None:
        """Test reading qualitative report from path."""
        from trading_platform.cli import cmd_ai_diagnose

        brief_path = tmp_path / "brief.json"
        qual_path = tmp_path / "qualitative.md"

        brief_data = {
            "backtest": {
                "run_id": "test",
                "trades": [],
                "metrics": {"total_pnl": -100},
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief_path.write_text(json.dumps(brief_data))
        qual_path.write_text("# Qualitative Analysis\n\nThis strategy needs work.")

        args = argparse.Namespace(
            brief=str(brief_path),
            qualitative_report_path=str(qual_path),
            qualitative_report=False,
            train=False,
        )

        with patch("trading_platform.cli.RuleBasedAnalyzer") as mock_analyzer_cls:
            mock_analyzer = MagicMock()
            mock_analyzer_cls.return_value = mock_analyzer
            mock_analyzer.generate_report_markdown.return_value = "# Report"
            mock_analyzer.generate_report_json.return_value = json.dumps(
                {"recommendations": []}
            )

            result = cmd_ai_diagnose(args)
            assert result == 0

    def test_qualitative_report_path_read_fails(self, tmp_path: Path) -> None:
        """Test when qualitative report path doesn't exist (lines 507-509)."""
        from trading_platform.cli import cmd_ai_diagnose

        brief_path = tmp_path / "brief.json"
        qual_path = tmp_path / "nonexistent.md"

        brief_data = {
            "backtest": {
                "run_id": "test",
                "trades": [],
                "metrics": {"total_pnl": -100},
                "config": {"instrument": {"symbol": "EUR_USD"}},
            },
        }
        brief_path.write_text(json.dumps(brief_data))

        args = argparse.Namespace(
            brief=str(brief_path),
            qualitative_report_path=str(qual_path),
            qualitative_report=False,
            train=False,
        )

        with patch("trading_platform.cli.RuleBasedAnalyzer") as mock_analyzer_cls:
            mock_analyzer = MagicMock()
            mock_analyzer_cls.return_value = mock_analyzer
            mock_analyzer.generate_report_markdown.return_value = "# Report"
            mock_analyzer.generate_report_json.return_value = json.dumps(
                {"recommendations": []}
            )

            result = cmd_ai_diagnose(args)
            # Should succeed with None for qualitative text
            assert result == 0
