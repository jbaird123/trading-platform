"""Tests for AI diagnostic CLI command.

# Validates: [AI-10.1], [AI-10.6.1]
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

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
        "suggested_parameters": {},
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


def test_cmd_ai_diagnose_qualitative_report_flag(tmp_path: Path):
    # 1. Create a dummy brief.json
    brief_content = {"meta": {"run_id": "test_run_123"}}
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(brief_content))

    # 2. Simulate command-line arguments with the new flag
    ns = Namespace(brief=str(brief_path), qualitative_report=True)

    # 3. Mock the LLM client to avoid real API calls
    with patch(
        "trading_platform.ai.llm_analysis.client.LlmApiClient"
    ) as mock_api_client:
        # Configure the mock instance
        mock_instance = mock_api_client.return_value
        mock_instance.get_feedback.return_value = "Mocked LLM response"

        # 4. Call the command
        with patch("builtins.print") as mock_print:
            return_code = cmd_ai_diagnose(ns)

            # 5. Assertions
            assert return_code == 0
            qualitative_report_path = tmp_path / "ai_qualitative_report.md"
            assert qualitative_report_path.exists()
            assert qualitative_report_path.read_text() == "Mocked LLM response"
            mock_print.assert_any_call("Generating qualitative report via LLM...")
            mock_print.assert_any_call(
                f"Qualitative report saved to {qualitative_report_path}"
            )


def test_cmd_ai_diagnose_triggers_specific_rule(tmp_path: Path) -> None:
    # 1. Create a brief.json designed to trigger the SignalPersistenceRule
    brief_content = {
        "signal_quality_analysis": {"signal_persistence_pct": 0.95},
        "meta": {
            "strategy_name": "PersistentSignalStrategy",
            "run_id": "test_run_456",
        },
    }
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(brief_content))

    # 2. Simulate command-line arguments
    ns = Namespace(brief=str(brief_path))

    # 3. Call the command function
    return_code = cmd_ai_diagnose(ns)

    # 4. Assertions
    assert return_code == 0
    md_report_path = tmp_path / "ai_diagnostic_report.md"
    assert md_report_path.exists()
    md_content = md_report_path.read_text()

    # Check that the specific rule's title and summary are in the report
    assert "Signal Persistence Detected" in md_content
    assert "Signals are persistent 95% of the time" in md_content
