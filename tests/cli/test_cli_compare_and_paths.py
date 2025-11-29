# Validates: [SYS-1.4.1], [SYS-1.7.2]
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd
from pytest import MonkeyPatch
from trading_platform.cli import cmd_compare, cmd_run_backtest, cmd_run_live
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


def _write_brief(path: Path, run_id: str, strat: str, total_pnl: float) -> None:
    data = {
        "meta": {"run_id": run_id, "strategy_name": strat},
        "overall_performance": {"total_pnl": total_pnl, "mean_pnl": 0.0},
        "equity_stats": {"max_drawdown": 0.0},
        "costs": {"total_costs": 0.0, "avg_cost_per_trade": 0.0},
        "exposure": {"average_gross_exposure": 0.0, "peak_gross_exposure": 0.0},
    }
    path.write_text(json.dumps(data))


def test_cmd_compare_success(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "out.html"
    _write_brief(a, "A", "S1", 10.0)
    _write_brief(b, "B", "S2", 20.0)
    ns = Namespace(a=str(a), b=str(b), out=str(out))
    rc = cmd_compare(ns)
    assert rc == 0 and out.exists()


def test_cmd_compare_missing_inputs(tmp_path: Path) -> None:
    ns = Namespace(
        a=str(tmp_path / "no.json"),
        b=str(tmp_path / "no2.json"),
        out=str(tmp_path / "out.html"),
    )
    rc = cmd_compare(ns)
    assert rc == 2


def test_cmd_run_backtest_reads_csv_path(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Test CLI can run backtest and produce artifacts.

    Note: run_backtest() now owns data loading from data_request.
    This test mocks run_backtest to focus on CLI artifact generation.
    """
    from unittest.mock import MagicMock, patch

    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)

    # Create a sample DataFrame for the mock
    df = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [1, 2, 3],
            "low": [1, 2, 3],
            "close": [1, 2, 3],
            "volume": [1, 1, 1],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC"),
    )

    cfg = {
        "user_id": "cli_csv",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "instrument": {"symbol": "EURUSD", "timeframe": "1H"},
        "data_request": {
            "symbol": "EURUSD",
            "timeframe": "1H",
            "start": "2024-01-01",
            "end": "2024-01-02",
        },
        "strategy": {
            "strategy_name": "TestStrat",
            "long_entry_rules": [
                {
                    "any_of": [
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
                    "any_of": [
                        {
                            "condition": "is_below",
                            "left": {"field": "close"},
                            "right": {"value": 2},
                        }
                    ]
                }
            ],
        },
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="cli_csv", config=str(cfg_path))

    # Mock run_backtest to return expected structure
    mock_strat = MagicMock()
    mock_strat.name = "TestStrat"
    mock_strat._feature_df = df
    mock_strat.generate_signals.return_value = pd.Series(
        [None, None, None], index=df.index
    )

    with patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
        "trading_platform.cli.compile_strategy"
    ) as mock_compile:
        mock_compile.return_value = mock_strat
        mock_backtest.return_value = {
            "trades": [],
            "equity_curve": [],
            "skipped": [],
            "strategy_name": "TestStrat",
            "initial_capital": 1000,
            "compiled_strategy": mock_strat,
            "feature_enriched_df": df,
            "market_data": df,
            "data_handler": None,
        }

        rc = cmd_run_backtest(ns)

    assert rc == 0
    # Ensure prices.csv and charts.html exist under the run directory
    runs_root = tmp_path / "cli_csv"
    # Find the single run directory
    run_dirs = [p for p in runs_root.iterdir() if p.is_dir()]
    assert run_dirs, "No run directory created"
    rp = run_dirs[0]
    assert (rp / "prices.csv").exists()
    assert (rp / "chart.html").exists()


def test_cmd_run_live_missing_config() -> None:
    ns = Namespace(config=None, dry_run=False)
    assert cmd_run_live(ns) == 2
