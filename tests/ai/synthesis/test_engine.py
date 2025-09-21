import pytest
import logging
import json
from unittest.mock import MagicMock, patch

from src.trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine
from src.trading_platform.ai.synthesis.rules import DiagnosticConclusion # Import actual class for type hinting

# Dummy classes for mocking rules and conclusions
class MockDiagnosticConclusion(DiagnosticConclusion):
    def __init__(self, title, summary, evidence):
        super().__init__(title, summary, evidence)

    def to_dict(self):
        return {"title": self.title, "summary": self.summary, "evidence": self.evidence}

class MockRule:
    def __init__(self, name="MockRule", conclusion_to_return=None):
        self.name = name
        self._conclusion_to_return = conclusion_to_return

    def evaluate(self, analysis_data):
        # Simulate rule evaluation logic
        if self._conclusion_to_return:
            return self._conclusion_to_return
        return None

# --- Tests for DiagnosticSynthesisEngine ---

def test_dse_init():
    analysis_data = {"some_data": 123}
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]) as mock_get_all_rules:
        engine = DiagnosticSynthesisEngine(analysis_data)
        assert engine.analysis_data == analysis_data
        assert engine.rules == []
        assert engine.conclusions == []
        mock_get_all_rules.assert_called_once()

def test_dse_run_no_rules(caplog):
    analysis_data = {"some_data": 123}
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]) as mock_get_all_rules:
        engine = DiagnosticSynthesisEngine(analysis_data)
        with caplog.at_level(logging.INFO):
            engine.run()
            assert "--- Running Diagnostic Synthesis Engine ---" in caplog.text
            assert "--- Engine run complete. ---" in caplog.text
            assert not engine.conclusions

def test_dse_run_rules_no_conclusions(caplog):
    analysis_data = {"some_data": 123}
    mock_rule1 = MockRule(name="Rule1", conclusion_to_return=None)
    mock_rule2 = MockRule(name="Rule2", conclusion_to_return=None)
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[mock_rule1, mock_rule2]) as mock_get_all_rules:
        engine = DiagnosticSynthesisEngine(analysis_data)
        with caplog.at_level(logging.INFO):
            engine.run()
            assert "Evaluating rule: MockRule..." in caplog.text # Called twice
            assert "Conclusion found" not in caplog.text
            assert not engine.conclusions
            mock_rule1.evaluate.assert_called_once_with(analysis_data)
            mock_rule2.evaluate.assert_called_once_with(analysis_data)

def test_dse_run_rules_with_conclusions(caplog):
    analysis_data = {"some_data": 123}
    
    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {"key1": "value1"})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {"key2": "value2"})
    
    mock_rule1 = MockRule(name="Rule1", conclusion_to_return=conc1)
    mock_rule2 = MockRule(name="Rule2", conclusion_to_return=None)
    mock_rule3 = MockRule(name="Rule3", conclusion_to_return=conc2)
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[mock_rule1, mock_rule2, mock_rule3]) as mock_get_all_rules:
        engine = DiagnosticSynthesisEngine(analysis_data)
        with caplog.at_level(logging.INFO):
            engine.run()
            assert len(engine.conclusions) == 2
            assert engine.conclusions[0] == conc1
            assert engine.conclusions[1] == conc2
            assert "Conclusion found: Title 1" in caplog.text
            assert "Conclusion found: Title 2" in caplog.text
            mock_rule1.evaluate.assert_called_once_with(analysis_data)
            mock_rule2.evaluate.assert_called_once_with(analysis_data)
            mock_rule3.evaluate.assert_called_once_with(analysis_data)

def test_dse_generate_report_markdown_no_conclusions():
    analysis_data = {"some_data": 123}
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        report = engine.generate_report_markdown()
        assert report == "# AI Diagnostic Report\n\nNo specific issues were detected by the diagnostic rules."

def test_dse_generate_report_markdown_with_one_conclusion():
    analysis_data = {"some_data": 123}
    conc = MockDiagnosticConclusion("Issue Title", "Issue Summary", {"metric": 0.1, "threshold": 0.5})
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[MockRule(conclusion_to_return=conc)]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()
        
        expected_report = (
            "# AI Diagnostic Report\n\n"
            "## Issue Title\n"
            "Issue Summary\n\n"
            "**Evidence:**\n"
            "```json\n{\n  \"metric\": 0.1,\n  \"threshold\": 0.5\n}\n```"
        )
        assert report == expected_report

def test_dse_generate_report_markdown_with_multiple_conclusions():
    analysis_data = {"some_data": 123}
    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {"key1": "value1"})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {"key2": "value2"})
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[
        MockRule(conclusion_to_return=conc1),
        MockRule(conclusion_to_return=conc2)
    ]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()
        
        expected_report_part1 = (
            "# AI Diagnostic Report\n\n"
            "## Title 1\n"
            "Summary 1\n\n"
            "**Evidence:**\n"
            "```json\n{\n  \"key1\": \"value1\"\n}\n```"
        )
        expected_report_part2 = (
            "## Title 2\n"
            "Summary 2\n\n"
            "**Evidence:**\n"
            "```json\n{\n  \"key2\": \"value2\"\n}\n```"
        )
        assert expected_report_part1 in report
        assert expected_report_part2 in report
        assert report.startswith("# AI Diagnostic Report")

def test_dse_generate_report_json_no_conclusions():
    analysis_data = {"some_data": 123}
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        report_json_str = engine.generate_report_json()
        assert json.loads(report_json_str) == []

def test_dse_generate_report_json_with_one_conclusion():
    analysis_data = {"some_data": 123}
    conc = MockDiagnosticConclusion("Issue Title", "Issue Summary", {"metric": 0.1})
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[MockRule(conclusion_to_return=conc)]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report_json_str = engine.generate_report_json()
        
        expected_json = [
            {"title": "Issue Title", "summary": "Issue Summary", "evidence": {"metric": 0.1}}
        ]
        assert json.loads(report_json_str) == expected_json

def test_dse_generate_report_json_with_multiple_conclusions():
    analysis_data = {"some_data": 123}
    conc1 = MockDiagnosticConclusion("Title 1", "Summary 1", {"key1": "value1"})
    conc2 = MockDiagnosticConclusion("Title 2", "Summary 2", {"key2": "value2"})
    
    with patch("src.trading_platform.ai.synthesis.engine.get_all_rules", return_value=[
        MockRule(conclusion_to_return=conc1),
        MockRule(conclusion_to_return=conc2)
    ]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report_json_str = engine.generate_report_json()
        
        expected_json = [
            {"title": "Title 1", "summary": "Summary 1", "evidence": {"key1": "value1"}},
            {"title": "Title 2", "summary": "Summary 2", "evidence": {"key2": "value2"}}
        ]
        assert json.loads(report_json_str) == expected_json
