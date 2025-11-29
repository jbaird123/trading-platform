# Validates: [SYS-1.7.2]
from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_run_backtest, main
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def test_cmd_run_backtest_missing_config() -> None:
    ns = Namespace(demo=False, user="u", config=None)
    assert cmd_run_backtest(ns) == 2


def test_cmd_run_backtest_yaml_requires_pyyaml(tmp_path: Path, monkeypatch) -> None:
    """Test CLI can load YAML config files.

    Note: run_backtest() now owns data loading from config.data_request.
    This test mocks run_backtest to focus on YAML parsing.
    """
    from unittest.mock import MagicMock, patch

    import pandas as pd

    # Write a minimal YAML config with data_request
    p = tmp_path / "cfg.yaml"
    p.write_text(
        "\n".join(
            [
                "user_id: yml_user",
                f"runs_dir: {tmp_path}",
                "initial_cash: 1000",
                "instrument:",
                "  symbol: EURUSD",
                "  timeframe: 1H",
                "data_request:",
                "  symbol: EURUSD",
                "  timeframe: 1H",
                "strategy:",
                "  strategy_name: S",
                "  long_entry_rules:",
                "    - any_of:",
                "        - condition: is_above",
                "          left:",
                "            value: 1",
                "          right:",
                "            value: 0",
                "  long_exit_rules:",
                "    - any_of:",
                "        - condition: is_below",
                "          left:",
                "            value: 1",
                "          right:",
                "            value: 2",
            ]
        )
    )

    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    ns = Namespace(demo=False, user="yml_user", config=str(p))

    # Create mock data
    mock_df = pd.DataFrame(
        {
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [1, 1],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )
    mock_strat = MagicMock()
    mock_strat.name = "S"
    mock_strat._feature_df = mock_df
    mock_strat.generate_signals.return_value = pd.Series(
        [None, None], index=mock_df.index
    )

    try:
        import yaml  # noqa: F401

        # If PyYAML is available, mock run_backtest and command should succeed.
        with patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
            "trading_platform.cli.compile_strategy"
        ) as mock_compile:
            mock_compile.return_value = mock_strat
            mock_backtest.return_value = {
                "trades": [],
                "equity_curve": [],
                "skipped": [],
                "strategy_name": "S",
                "initial_capital": 1000,
                "compiled_strategy": mock_strat,
                "feature_enriched_df": mock_df,
                "market_data": mock_df,
                "data_handler": None,
            }
            rc = cmd_run_backtest(ns)
        assert rc == 0
    except ImportError:
        # Without PyYAML, _load_config should raise SystemExit
        try:
            cmd_run_backtest(ns)
            assert False, "Expected SystemExit due to missing PyYAML"
        except SystemExit:
            pass


def test_cli_main_compare_invokes_subcommand(tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "out.html"
    a.write_text(json.dumps({"meta": {"run_id": "A", "strategy_name": "S"}}))
    b.write_text(json.dumps({"meta": {"run_id": "B", "strategy_name": "S"}}))
    argv = ["tp", "compare", str(a), str(b), "--out", str(out)]
    monkeypatch.setenv("PYTHONWARNINGS", "ignore")
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0 and out.exists()
