from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_run_backtest, cmd_run_live
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
        risk={},
    )


def test_cmd_run_backtest_demo(tmp_path: Path) -> None:
    ns = Namespace(demo=True, user="cli_demo", config=None)
    rc = cmd_run_backtest(ns)
    assert rc == 0


def test_cmd_run_backtest_config_minimal(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    cfg_obj = {
        "user_id": "cli_cfg",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "strategy": {
            "strategy_name": "TestStrat",
            "long_entry_rules": [
                {
                    "any_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 1.5,
                        }
                    ]
                }
            ],
            "long_exit_rules": [
                {
                    "any_of": [
                        {
                            "condition": "is_below",
                            "left": "close",
                            "right": 1.5,
                        }
                    ]
                }
            ],
        },
    }
    cfg_path.write_text(json.dumps(cfg_obj))
    ns = Namespace(demo=False, user="cli_cfg", config=str(cfg_path))
    rc = cmd_run_backtest(ns)
    assert rc == 0
    # Verify artifacts exist
    # run_id folder is dynamic; check brief presence under user dir
    user_dir = tmp_path / "cli_cfg"
    assert user_dir.exists()
    # Find any run dir with a brief.json
    briefs = list(user_dir.rglob("brief.json"))
    assert briefs, "brief.json not written for config run"


def test_cmd_run_live_dry_run() -> None:
    ns = Namespace(config=None, dry_run=True)
    assert cmd_run_live(ns) == 0


def test_cmd_run_live_stub_with_config(tmp_path: Path) -> None:
    cfg = tmp_path / "live.json"
    live_cfg = {
        "user_id": "cli_live",
        "runs_dir": str(tmp_path),
        "blackout_utc": [["23:00", "01:00"]],
    }
    cfg.write_text(json.dumps(live_cfg))
    ns = Namespace(config=str(cfg), dry_run=False)
    assert cmd_run_live(ns) == 0
