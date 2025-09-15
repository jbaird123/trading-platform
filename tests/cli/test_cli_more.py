from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_run_backtest, main


def test_cmd_run_backtest_missing_config() -> None:
    ns = Namespace(demo=False, user="u", config=None)
    assert cmd_run_backtest(ns) == 2


def test_cmd_run_backtest_yaml_requires_pyyaml(tmp_path: Path) -> None:
    # Write a minimal YAML config (PyYAML may or may not be installed)
    p = tmp_path / "cfg.yaml"
    p.write_text(
        "\n".join(
            [
                "user_id: yml_user",
                f"runs_dir: {tmp_path}",
                "initial_cash: 1000",
                "strategy:",
                "  strategy_name: S",
                "  long_entry_rules:",
                "    - any_of:",
                "        - condition: is_above",
                "          left: 1",
                "          right: 0",
                "  long_exit_rules:",
                "    - any_of:",
                "        - condition: is_below",
                "          left: 1",
                "          right: 2",
            ]
        )
    )
    ns = Namespace(demo=False, user="yml_user", config=str(p))
    try:
        import yaml  # type: ignore  # noqa: F401

        # If PyYAML is available, command should succeed.
        rc = cmd_run_backtest(ns)
        assert rc == 0
    except Exception:
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
