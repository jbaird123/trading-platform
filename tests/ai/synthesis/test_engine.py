import json
import logging
from unittest.mock import MagicMock, patch

from src.trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine
from src.trading_platform.ai.synthesis.recommendations import Recommendation
from src.trading_platform.ai.synthesis.rules import (
    DiagnosticConclusion,  # Import actual class for type hinting
)


# Dummy classes for mocking rules and conclusions
class MockDiagnosticConclusion(DiagnosticConclusion):
    def __init__(self, title, summary, evidence):
        super().__init__(title, summary, evidence)

    def to_dict(self):
        return {"title": self.title, "summary": self.summary, "evidence": self.evidence}


class MockRule:
    def __init__(self, name="MockRule", conclusion_to_return=None):
        self.name = name
        self.evaluate = MagicMock(return_value=conclusion_to_return)


# --- Tests for DiagnosticSynthesisEngine ---


def test_dse_init():
    analysis_data = {"some_data": 123}

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        assert engine.analysis_data == analysis_data
        assert engine.rules == []
        assert engine.conclusions == []


def test_dse_run_no_rules(caplog):
    analysis_data = {"some_data": 123}

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        with caplog.at_level(logging.INFO):
            engine.run()
            log_text = "".join(record.message for record in caplog.records)
            assert "--- Running Diagnostic Synthesis Engine ---" in log_text
            assert "--- Engine run complete. ---" in log_text
            assert not engine.conclusions


def test_dse_run_rules_no_conclusions(caplog):
    analysis_data = {"some_data": 123}
    mock_rule1 = MockRule(name="Rule1")
    mock_rule2 = MockRule(name="Rule2")

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[mock_rule1, mock_rule2],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        with caplog.at_level(logging.INFO):
            engine.run()
            log_text = "".join(record.message for record in caplog.records)
            assert "Evaluating rule: " in log_text
            assert "Conclusion found" not in log_text
            assert not engine.conclusions
            mock_rule1.evaluate.assert_called_once_with(analysis_data)
            mock_rule2.evaluate.assert_called_once_with(analysis_data)


def test_dse_run_rules_with_conclusions(caplog):
    analysis_data = {"some_data": 123}

    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {"key1": "value1"})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {"key2": "value2"})

    mock_rule1 = MockRule(name="Rule1", conclusion_to_return=conc1)
    mock_rule2 = MockRule(name="Rule2")
    mock_rule3 = MockRule(name="Rule3", conclusion_to_return=conc2)

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[mock_rule1, mock_rule2, mock_rule3],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        with caplog.at_level(logging.INFO):
            engine.run()
            log_text = "".join(record.message for record in caplog.records)
            assert len(engine.conclusions) == 2
            assert engine.conclusions[0] == conc1
            assert engine.conclusions[1] == conc2
            assert "Conclusion found: Title 1" in log_text
            assert "Conclusion found: Title 2" in log_text
            mock_rule1.evaluate.assert_called_once_with(analysis_data)
            mock_rule2.evaluate.assert_called_once_with(analysis_data)
            mock_rule3.evaluate.assert_called_once_with(analysis_data)


def test_dse_generate_report_markdown_no_conclusions():
    analysis_data = {"some_data": 123}
    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        report = engine.generate_report_markdown()
        assert report == (
            "# AI Diagnostic Report\n\nNo specific issues were detected by "
            "the diagnostic rules."
        )


def test_dse_generate_report_markdown_with_one_conclusion():
    analysis_data = {"some_data": 123}
    conc = MockDiagnosticConclusion(
        "Issue Title", "Issue Summary", {"metric": 0.1, "threshold": 0.5}
    )
    rec = Recommendation("Issue Title", "Issue Summary", "default_category", 1.0)

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ), patch(
        "src.trading_platform.ai.synthesis.engine.generate_recommendations",
        return_value=[rec],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()

        expected_report = (
            "# AI Diagnostic Report\n\n"
            "## Recommendations\n\n"
            "### Issue Title\n"
            "Issue Summary\n\n"
            "- Category: default_category\n"
            "- Confidence: 1.0\n"
            "\n"
            "## Issue Title\n"
            "Issue Summary\n\n"
            "**Evidence:**\n"
            "- metric: 0.1\n"
            "- threshold: 0.5"
        )
        assert report == expected_report


def test_dse_generate_report_markdown_with_multiple_conclusions():
    analysis_data = {"some_data": 123}
    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {"key1": "value1"})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {"key2": "value2"})

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[
            MockRule(conclusion_to_return=conc1),
            MockRule(conclusion_to_return=conc2),
        ],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()

        expected_report_part1 = (
            "## Title 1\n" "Summary 1\n\n" "**Evidence:**\n" "- key1: value1"
        )
        expected_report_part2 = (
            "## Title 2\n" "Summary 2\n\n" "**Evidence:**\n" "- key2: value2"
        )
        assert expected_report_part1 in report
        assert expected_report_part2 in report
        assert report.startswith("# AI Diagnostic Report")


def test_dse_generate_report_json_no_conclusions():
    analysis_data = {"some_data": 123}
    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        report_json_str = engine.generate_report_json()
    assert json.loads(report_json_str) == {
        "conclusions": [],
        "recommendations": [],
        "model_insights": [],
        "suggested_parameters": {},
    }


def test_dse_generate_report_json_with_one_conclusion():
    analysis_data = {"some_data": 123}
    conc = MockDiagnosticConclusion("Issue Title", "Issue Summary", {"metric": 0.1})

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report_json_str = engine.generate_report_json()

        expected_json = {
            "conclusions": [
                {
                    "title": "Issue Title",
                    "summary": "Issue Summary",
                    "evidence": {"metric": 0.1},
                }
            ],
            "recommendations": [],
            "model_insights": [],
            "suggested_parameters": {},
        }
        assert json.loads(report_json_str) == expected_json


def test_dse_generate_report_json_with_multiple_conclusions():
    analysis_data = {"some_data": 123}
    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {"key1": "value1"})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {"key2": "value2"})

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[
            MockRule(conclusion_to_return=conc1),
            MockRule(conclusion_to_return=conc2),
        ],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report_json_str = engine.generate_report_json()

        expected_json = {
            "conclusions": [
                {
                    "title": "Title 1",
                    "summary": "Summary 1",
                    "evidence": {"key1": "value1"},
                },
                {
                    "title": "Title 2",
                    "summary": "Summary 2",
                    "evidence": {"key2": "value2"},
                },
            ],
            "recommendations": [],
            "model_insights": [],
            "suggested_parameters": {},
        }
        assert json.loads(report_json_str) == expected_json


def test_dse_generate_recommendations():
    """Test the generation of recommendations from conclusions."""
    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {})

    engine = DiagnosticSynthesisEngine({})
    engine.conclusions = [conc1, conc2]
    recommendations = engine.generate_recommendations()

    assert len(recommendations) == 2
    assert recommendations[0]["title"] == "Title 1"
    assert recommendations[0]["description"] == "Summary 1"
    assert recommendations[1]["title"] == "Title 2"


def test_dse_generate_report_markdown_with_recommendations():
    """Test that the markdown report includes recommendations."""
    analysis_data = {"some_data": 123}
    conc = MockDiagnosticConclusion("Rec Title", "Rec Summary", {})
    rec = Recommendation("Rec Title", "Rec Summary", "Test Category", 0.99)

    with patch(
        "src.trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ), patch(
        "src.trading_platform.ai.synthesis.engine.generate_recommendations",
        return_value=[rec],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()  # This will generate recommendations

        report = engine.generate_report_markdown()

        assert "## Recommendations" in report
        assert "### Rec Title" in report
        assert "Rec Summary" in report
        assert "- Category: Test Category" in report
        assert "- Confidence: 0.99" in report
