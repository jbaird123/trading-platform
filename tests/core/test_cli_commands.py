# Validates: [SYS-1.7.2], [RV-9.1]
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from pytest import MonkeyPatch
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
        parameters={},
    )


def test_cmd_run_backtest_demo(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    ns = Namespace(demo=True, user="cli_demo", config=None)
    rc = cmd_run_backtest(ns)
    assert rc == 0


def test_cmd_run_backtest_config_minimal(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    cfg_path = tmp_path / "cfg.json"
    cfg_obj = {
        "user_id": "cli_cfg",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "instrument": {"symbol": "EURUSD"},
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
    # Ensure parameters field exists
    strategy_dict = cfg_obj["strategy"]
    if isinstance(strategy_dict, dict):
        strategy_dict["parameters"] = strategy_dict.get("parameters", {})
    rc = cmd_run_backtest(ns)
    assert rc == 0
    # Verify artifacts exist
    # run_id folder is dynamic; check brief presence under user dir
    user_dir = tmp_path / "cli_cfg"
    assert user_dir.exists()
    # Find any run dir with a brief.json
    briefs = list(user_dir.rglob("brief.json"))
    assert briefs, "brief.json not written for config run"


def test_cmd_run_backtest_saves_signals_artifact(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    cfg_path = tmp_path / "cfg.json"
    cfg_obj = {
        "user_id": "cli_cfg_signals",
        "runs_dir": str(tmp_path),
        "instrument": {"symbol": "EURUSD"},
        "strategy": {
            "strategy_name": "TestStrat",
            "long_entry_rules": [
                {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
            ],
            "long_exit_rules": [
                {"any_of": [{"condition": "is_below", "left": "close", "right": 0}]}
            ],
        },
    }
    cfg_path.write_text(json.dumps(cfg_obj))
    ns = Namespace(demo=False, user="cli_cfg_signals", config=str(cfg_path))
    # Ensure parameters field exists
    strategy_dict = cfg_obj["strategy"]
    if isinstance(strategy_dict, dict):
        strategy_dict["parameters"] = strategy_dict.get("parameters", {})
    rc = cmd_run_backtest(ns)
    assert rc == 0

    user_dir = tmp_path / "cli_cfg_signals"
    briefs = list(user_dir.rglob("brief.json"))
    assert briefs
    brief_path = briefs[0]
    run_path = brief_path.parent

    signals_parquet_path = run_path / "signals.parquet"
    assert signals_parquet_path.exists()

    brief_data = json.loads(brief_path.read_text())
    artifacts = brief_data.get("artifacts", {})
    assert "signals_path" in artifacts
    assert artifacts["signals_path"] == str(signals_parquet_path)


def test_cmd_run_backtest_saves_rmm_spans_artifact(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    cfg_path = tmp_path / "cfg.json"
    cfg_obj = {
        "user_id": "cli_cfg_rmm_spans",
        "runs_dir": str(tmp_path),
        "instrument": {"symbol": "EURUSD"},
        "strategy": {
            "strategy_name": "TestStrat",
            "long_entry_rules": [
                {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
            ],
            "long_exit_rules": [
                {"any_of": [{"condition": "is_below", "left": "close", "right": 0}]}
            ],
        },
        "rmm_config": {
            "regimes": [
                {
                    "label": "daily_trend",
                    "conditions": {
                        "all_of": [
                            {"condition": "is_above", "left": "close", "right": 0}
                        ]
                    },
                    "confidence": 1.0,
                }
            ],
            "policy": {},
        },
    }
    cfg_path.write_text(json.dumps(cfg_obj))
    ns = Namespace(demo=False, user="cli_cfg_rmm_spans", config=str(cfg_path))
    # Ensure parameters field exists
    strategy_dict = cfg_obj["strategy"]
    if isinstance(strategy_dict, dict):
        strategy_dict["parameters"] = strategy_dict.get("parameters", {})
    rc = cmd_run_backtest(ns)
    assert rc == 0

    user_dir = tmp_path / "cli_cfg_rmm_spans"
    briefs = list(user_dir.rglob("brief.json"))
    assert briefs
    brief_path = briefs[0]
    run_path = brief_path.parent

    rmm_spans_path = run_path / "rmm_spans.json"
    assert rmm_spans_path.exists()

    brief_data = json.loads(brief_path.read_text())
    artifacts = brief_data.get("artifacts", {})
    assert "rmm_spans_path" in artifacts
    assert artifacts["rmm_spans_path"] == str(rmm_spans_path)


def test_cmd_run_live_dry_run() -> None:
    ns = Namespace(config=None, dry_run=True)
    assert cmd_run_live(ns) == 0


def test_cmd_run_live_stub_with_config(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    cfg = tmp_path / "live.json"
    live_cfg = {
        "user_id": "cli_live",
        "runs_dir": str(tmp_path),
        "instrument": {"symbol": "EURUSD"},
        "blackout_utc": [["23:00", "01:00"]],
    }
    cfg.write_text(json.dumps(live_cfg))
    ns = Namespace(config=str(cfg), dry_run=False)
    assert cmd_run_live(ns) == 0
