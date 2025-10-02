"""Integration tests for CLI commands covering realistic usage scenarios."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def test_cmd_run_backtest_minimal_integration(tmp_path: Path) -> None:
    """Test cmd_run_backtest with minimal valid configuration."""
    # Validates: [REQ-CLI-INT-001] Run backtest with minimal config
    config_path = tmp_path / "config.json"
    config = {
        "run_id": "test",
        "instrument": {"symbol": "EURUSD"},
        "initial_cash": 100000,
        "strategy": {
            "strategy_name": "Test",
            "long_entry_rules": [{"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}],
            "long_exit_rules": [{"any_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}],
            "short_entry_rules": [],
            "short_exit_rules": [],
            "features": [],
        },
    }
    config_path.write_text(json.dumps(config))

    import argparse
    args = argparse.Namespace(demo=False, config=str(config_path), user="test")

    # Mock the entire pipeline with valid returns
    with patch("trading_platform.cli.initialize_run") as mock_init, \
         patch("trading_platform.cli.finalize_run") as mock_final, \
         patch("trading_platform.cli.run_backtest") as mock_backtest, \
         patch("trading_platform.cli.compile_strategy") as mock_compile, \
         patch("trading_platform.data.loader.load_instrument_data") as mock_load:

        run_path = tmp_path / "runs/test"
        run_path.mkdir(parents=True)
        mock_init.return_value = run_path

        # Mock data
        df = pd.DataFrame({
            "open": [1.0, 1.1, 1.2],
            "high": [1.05, 1.15, 1.25],
            "low": [0.95, 1.05, 1.15],
            "close": [1.02, 1.12, 1.22],
            "volume": [100, 110, 120],
        }, index=pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"))
        mock_load.return_value = (df, [])

        # Mock strategy
        mock_strat = MagicMock()
        mock_strat.name = "Test"
        mock_strat.generate_signals.return_value = pd.Series([0, 1, -1])
        mock_compile.return_value = mock_strat

        # Mock backtest
        mock_backtest.return_value = []

        from trading_platform.cli import cmd_run_backtest
        result = cmd_run_backtest(args)

        assert result == 0
        mock_init.assert_called_once()
        mock_compile.assert_called_once()
        mock_backtest.assert_called_once()
        mock_final.assert_called_once()


def test_cmd_ai_diagnose_with_brief(tmp_path: Path) -> None:
    """Test cmd_ai_diagnose loads and processes brief."""
    # Validates: [REQ-CLI-DIAGNOSE-001] Load and diagnose brief
    brief_path = tmp_path / "brief.json"
    brief = {
        "meta": {"run_id": "test", "strategy_name": "Test"},
        "performance": {"total_pnl": 1000, "sharpe_ratio": 1.5},
        "trades": [],
    }
    brief_path.write_text(json.dumps(brief))

    import argparse
    args = argparse.Namespace(brief=str(brief_path), train_model=False)

    with patch("trading_platform.cli.DiagnosticSynthesisEngine") as mock_engine:
        mock_instance = MagicMock()
        mock_instance.generate_report_markdown.return_value = "Diagnosis: Good strategy"
        mock_instance.generate_report_json.return_value = json.dumps({
            "recommendations": ["Test recommendation"]
        })
        mock_engine.return_value = mock_instance

        from trading_platform.cli import cmd_ai_diagnose
        result = cmd_ai_diagnose(args)

        assert result == 0
        mock_engine.assert_called_once()


def test_cmd_ai_diagnose_missing_brief() -> None:
    """Test cmd_ai_diagnose raises error when brief missing."""
    # Validates: [REQ-CLI-DIAGNOSE-002] Validate brief path
    import argparse
    args = argparse.Namespace(brief=None, train_model=False)

    from trading_platform.cli import cmd_ai_diagnose

    with pytest.raises(ValueError, match="--brief is required"):
        cmd_ai_diagnose(args)


def test_cmd_ai_diagnose_nonexistent_brief(tmp_path: Path) -> None:
    """Test cmd_ai_diagnose raises error for nonexistent brief."""
    # Validates: [REQ-CLI-DIAGNOSE-003] Validate brief exists
    import argparse
    args = argparse.Namespace(brief=str(tmp_path / "missing.json"), train_model=False)

    from trading_platform.cli import cmd_ai_diagnose

    with pytest.raises(ValueError, match="No such file"):
        cmd_ai_diagnose(args)


def test_cmd_compare_with_explicit_paths(tmp_path: Path) -> None:
    """Test cmd_compare with explicit brief paths."""
    # Validates: [REQ-CLI-COMPARE-001] Compare explicit briefs
    brief_a = tmp_path / "a.json"
    brief_b = tmp_path / "b.json"

    brief_a.write_text(json.dumps({"meta": {"run_id": "a"}, "performance": {}}))
    brief_b.write_text(json.dumps({"meta": {"run_id": "b"}, "performance": {}}))

    import argparse
    args = argparse.Namespace(
        a=str(brief_a),
        b=str(brief_b),
        out=str(tmp_path / "comp.html"),
        last=0,
        runs_dir="runs",
        user=None,
    )

    with patch("trading_platform.cli.save_comparison_report") as mock_save:
        from trading_platform.cli import cmd_compare
        result = cmd_compare(args)

        assert result == 0
        mock_save.assert_called_once()


def test_cmd_compare_missing_brief_returns_error(tmp_path: Path) -> None:
    """Test cmd_compare returns error when brief missing."""
    # Validates: [REQ-CLI-COMPARE-002] Validate brief paths
    import argparse
    args = argparse.Namespace(
        a=str(tmp_path / "missing.json"),
        b=str(tmp_path / "also_missing.json"),
        out="out.html",
        last=0,
        runs_dir="runs",
        user=None,
    )

    from trading_platform.cli import cmd_compare
    result = cmd_compare(args)

    assert result == 2


def test_cmd_open_chart_generates_when_missing(tmp_path: Path) -> None:
    """Test cmd_open_chart generates chart when not exists."""
    # Validates: [REQ-CLI-CHART-001] Generate missing chart
    runs_dir = tmp_path / "runs/user1"
    run_dir = runs_dir / "run_0"
    run_dir.mkdir(parents=True)

    brief = run_dir / "brief.json"
    brief.write_text(json.dumps({
        "meta": {"run_id": "run_0"},
        "equity_stats": {"equity_curve": [["2024-01-01", 100000]]},
        "trades": [],
    }))

    import argparse
    args = argparse.Namespace(
        runs_dir=str(tmp_path / "runs"),
        user="user1",
        last=1,
        open=False,
    )

    from trading_platform.cli import cmd_open_chart
    result = cmd_open_chart(args)

    assert result == 0
    chart_path = run_dir / "chart.html"
    assert chart_path.exists()
