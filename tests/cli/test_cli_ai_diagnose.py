from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_ai_diagnose


def test_cmd_ai_diagnose_success(tmp_path: Path) -> None:
    # 1. Create a dummy brief.json file
    brief_content = {
        "overall_performance": {
            "n_trades": 100,
            "total_pnl": 500.0,
            "mean_pnl": 5.0,
            "win_rate": 0.6,
        },
        "meta": {
            "strategy_name": "TestStrategy",
            "run_id": "test_run_123",
        },
    }
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(brief_content))

    # 2. Simulate command-line arguments
    ns = Namespace(brief=str(brief_path))

    # 3. Call the command function directly
    return_code = cmd_ai_diagnose(ns)

    # 4. Assertions
    assert return_code == 0, f"Expected return code 0, but got {return_code}"

    # Assert that report files are created
    md_report_path = tmp_path / "ai_diagnostic_report.md"
    json_report_path = tmp_path / "ai_diagnostic_report.json"

    assert md_report_path.exists()
    assert json_report_path.exists()

    # Optionally, assert on content (e.g., no issues detected for this dummy brief)
    md_content = md_report_path.read_text()
    json_content = json_report_path.read_text()

    assert "No specific issues were detected by the diagnostic rules." in md_content
    assert json.loads(json_content) == {
        "conclusions": [],
        "recommendations": [],
        "model_insights": [],
    }  # No conclusions means empty list


def test_cmd_ai_diagnose_missing_brief(tmp_path):
    from argparse import Namespace

    ns = Namespace(brief=None)
    try:
        cmd_ai_diagnose(ns)
    except Exception as e:
        assert "brief" in str(e).lower() or isinstance(e, SystemExit)
    else:
        assert False, "Expected error when --brief is not provided"


def test_cmd_ai_diagnose_invalid_brief_path(tmp_path):
    from argparse import Namespace

    ns = Namespace(brief=str(tmp_path / "nonexistent.json"))
    try:
        cmd_ai_diagnose(ns)
    except Exception as e:
        assert "no such file" in str(e).lower() or isinstance(e, SystemExit)
    else:
        assert False, "Expected error for invalid brief path"


def test_cmd_ai_diagnose_malformed_json(tmp_path):
    from argparse import Namespace

    brief_path = tmp_path / "brief.json"
    brief_path.write_text("{not: valid json}")
    ns = Namespace(brief=str(brief_path))
    try:
        cmd_ai_diagnose(ns)
    except Exception as e:
        assert "json" in str(e).lower() or isinstance(e, SystemExit)
    else:
        assert False, "Expected error for malformed JSON"
