from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_run_backtest


def test_cmd_run_backtest_toy_data_path(tmp_path: Path) -> None:
    cfg = {
        "user_id": "toy_user",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "strategy": {
            "strategy_name": "S",
            "entry_rules": [
                {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
            ],
            "exit_rules": [
                {"any_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
            ],
        },
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="toy_user", config=str(p))
    rc = cmd_run_backtest(ns)
    assert rc == 0
