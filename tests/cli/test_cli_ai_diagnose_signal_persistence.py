import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_ai_diagnose


def test_cmd_ai_diagnose_triggers_signal_persistence_rule(tmp_path: Path) -> None:
    # Create a brief.json that triggers SignalPersistenceRule
    brief_content = {
        "signal_quality_analysis": {"signal_persistence_pct": 0.85},
        "meta": {"strategy_name": "TestStrategy", "run_id": "test_run_456"},
    }
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(brief_content))

    ns = Namespace(brief=str(brief_path))
    return_code = cmd_ai_diagnose(ns)
    assert return_code == 0

    md_report_path = tmp_path / "ai_diagnostic_report.md"
    assert md_report_path.exists()
    md_content = md_report_path.read_text()
    assert "Signal Persistence Detected" in md_content
    assert "persistent 85% of the time" in md_content
