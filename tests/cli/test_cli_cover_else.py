# Validates: [SYS-1.7.2]
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import trading_platform.cli as cli
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


def test_cmd_run_backtest_else_branch(tmp_path: Path, monkeypatch) -> None:
    # Force run_backtest to return non-tuple to exercise else branch
    monkeypatch.setattr(cli, "run_backtest", lambda *a, **k: [])

    called = {"finalize": False}

    def fake_finalize(*args, **kwargs):
        called["finalize"] = True

    monkeypatch.setattr(cli, "finalize_run", fake_finalize)

    cfg = {
        "user_id": "else_user",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [
                {"any_of": [{"condition": "is_above", "left": 2, "right": 3}]}
            ],
            "long_exit_rules": [
                {"any_of": [{"condition": "is_below", "left": 2, "right": 1}]}
            ],
        },
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="else_user", config=str(p))
    # Ensure parameters field exists
    strategy_dict = cfg["strategy"]
    if isinstance(strategy_dict, dict):
        strategy_dict["parameters"] = strategy_dict.get("parameters", {})
    rc = cli.cmd_run_backtest(ns)
    assert rc == 0 and called["finalize"]
