# Validates: [RV-9.4]
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_open_chart


def test_cmd_open_chart_generates_when_missing(tmp_path: Path) -> None:
    run = tmp_path / "u" / "r1"
    run.mkdir(parents=True, exist_ok=True)
    brief = {
        "meta": {"run_id": "r1", "strategy_name": "S"},
        "equity_stats": {
            "equity_curve": [["2023-01-01T00:00:00", 1000.0]],
        },
        "trades": [],
    }
    (run / "brief.json").write_text(json.dumps(brief))
    ns = Namespace(runs_dir=str(tmp_path), user="u", last=1, open=False)
    rc = cmd_open_chart(ns)
    assert rc == 0
    out = run / "chart.html"
    assert out.exists() and "lightweight-charts" in out.read_text()
