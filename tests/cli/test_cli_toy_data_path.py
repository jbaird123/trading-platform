# Validates: [SYS-1.7.2]
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_run_backtest
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
    )


def test_cmd_run_backtest_toy_data_path(tmp_path: Path) -> None:
    cfg = {
        "user_id": "toy_user",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [
                {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
            ],
            "long_exit_rules": [
                {"any_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
            ],
        },
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="toy_user", config=str(p))
    rc = cmd_run_backtest(ns)
    assert rc == 0


def test_cmd_run_backtest_demo_flag(tmp_path: Path) -> None:
    ns = Namespace(demo=True, user="demo_user", config=None)
    rc = cmd_run_backtest(ns)
    assert rc == 0
