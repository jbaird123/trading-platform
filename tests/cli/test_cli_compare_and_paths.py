from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd
from trading_platform.cli import cmd_compare, cmd_run_backtest, cmd_run_live


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


def test_cmd_run_backtest_reads_csv_path(tmp_path: Path) -> None:
    # Prepare a tiny OHLCV CSV
    csv = tmp_path / "data.csv"
    df = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [1, 2, 3],
            "low": [1, 2, 3],
            "close": [1, 2, 3],
            "volume": [1, 1, 1],
        }
    )
    df.to_csv(csv, index_label="ts")

    cfg = {
        "user_id": "cli_csv",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "data": {"csv_path": str(csv)},
        "strategy": {
            "strategy_name": "TestStrat",
            "long_entry_rules": [
                {"any_of": [{"condition": "is_above", "left": "close", "right": 1}]}
            ],
            "long_exit_rules": [
                {"any_of": [{"condition": "is_below", "left": "close", "right": 2}]}
            ],
        },
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="cli_csv", config=str(cfg_path))
    rc = cmd_run_backtest(ns)
    assert rc == 0


def test_cmd_run_live_missing_config() -> None:
    ns = Namespace(config=None, dry_run=False)
    assert cmd_run_live(ns) == 2
