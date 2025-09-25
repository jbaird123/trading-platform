import json
import logging
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine
from trading_platform.ai.synthesis.recommendations import Recommendation
from trading_platform.ai.synthesis.rules import (
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

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        assert engine.analysis_data == analysis_data
        assert engine.rules == []
        assert engine.conclusions == []


def test_dse_run_no_rules(caplog):
    analysis_data = {"some_data": 123}

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[mock_rule1, mock_rule2],
    ):
        caplog.set_level(logging.INFO, logger="trading_platform.ai.synthesis.engine")
        engine = DiagnosticSynthesisEngine(analysis_data)
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[mock_rule1, mock_rule2, mock_rule3],
    ):
        caplog.set_level(logging.INFO, logger="trading_platform.ai.synthesis.engine")
        engine = DiagnosticSynthesisEngine(analysis_data)
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
    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ), patch(
        "trading_platform.ai.synthesis.engine.generate_recommendations",
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
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
    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
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
        "trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ), patch(
        "trading_platform.ai.synthesis.engine.generate_recommendations",
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


def test_engine_with_empty_brief():
    """Test DiagnosticSynthesisEngine with empty analysis_data."""
    analysis_data: Dict[str, Any] = {}

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        assert engine.conclusions == []
        assert engine.recommendations == []


def test_engine_with_brief_missing_trades():
    """Test engine with a brief that has no trades key."""
    # Initialize engine with analysis data missing trades key
    analysis_data = {"backtest_metrics": {"n_trades": 0, "win_rate": 0.0}}

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()

        # Generate JSON report to check model_insights
        report_json_str = engine.generate_report_json()
        report_data = json.loads(report_json_str)

        # Assert that engine runs successfully and model_insights is empty list
        assert report_data["model_insights"] == []
        assert engine.conclusions == []
        assert engine.recommendations == []


def test_dse_parameter_suggestion_exception():
    """Test parameter suggestion exception handling - covers lines 68-69."""
    analysis_data = {"some_data": 123}

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("trading_platform.ai.lab.param_suggester.suggest_parameters", 
               side_effect=ImportError("Module not found")), \
         patch("trading_platform.ai.synthesis.engine.logger.warning") as mock_warning:
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        
        # Should handle the exception and log a warning
        mock_warning.assert_called_with("Failed to suggest parameters: Module not found")
        assert engine.suggested_parameters == {}


def test_dse_model_insights_no_run_dir():
    """Test model insights when run directory doesn't exist - covers lines 78-80."""
    analysis_data = {
        "meta": {"run_id": "test123"},
        "_brief_path": "/nonexistent/path",
        "trades": []
    }

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("pathlib.Path") as mock_path_class:
        
        # Set up Path mocking for non-existent run dir
        mock_run_dir = MagicMock()
        mock_run_dir.exists.return_value = False  # Run dir doesn't exist
        mock_model_path = MagicMock()
        mock_model_path.exists.return_value = False  # Model doesn't exist either
        
        def path_side_effect(x):
            if x == "/nonexistent/path":
                return mock_run_dir
            return mock_model_path
        
        mock_path_class.side_effect = path_side_effect
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        
        # Should not generate any model insights
        assert engine.model_insights == []


def test_dse_model_insights_no_model_file():
    """Test when model file doesn't exist - covers line 87."""
    analysis_data: dict[str, list[dict[str, float]]] = {"trades": []}

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("pathlib.Path") as mock_path_class:
        
        # Set up Path mocking for non-existent model
        mock_model_path = MagicMock()
        mock_model_path.exists.return_value = False  # Model file doesn't exist
        mock_path_class.return_value = mock_model_path
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        
        # Should not generate any model insights
        assert engine.model_insights == []


def test_dse_model_insights_run_dir_exists():
    """Test model insights when run directory exists and has model - covers lines 84-86."""
    analysis_data = {
        "meta": {"run_id": "test123"},
        "_brief_path": "/tmp/test_run"
    }

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("pathlib.Path") as mock_path_class, \
         patch("joblib.load", side_effect=Exception("Skip actual loading")):
        
        # Set up Path mocking
        mock_run_dir = MagicMock()
        mock_run_dir.exists.return_value = True
        mock_model_path = MagicMock()
        mock_model_path.exists.return_value = True
        mock_run_dir.__truediv__ = MagicMock(return_value=mock_model_path)
        
        def path_side_effect(x):
            if x == "/tmp/test_run":
                return mock_run_dir
            return mock_model_path
            
        mock_path_class.side_effect = path_side_effect
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        
        # The constructor should attempt to load the model (will fail due to mocked exception)
        # This covers lines 84-86 where candidate path is set and checked
        assert engine.model_insights == []


def test_dse_model_insights_successful_load_no_trades():
    """Test model loading success path but no trades to process - covers lines 93-107."""
    analysis_data: dict[str, list[dict[str, float]]] = {"trades": []}  # Empty trades list

    # Mock the model loading to succeed but avoid the complex dependencies
    mock_model = MagicMock()
    mock_model.feature_names_in_ = ["feature1", "feature2"]

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("pathlib.Path") as mock_path_class, \
         patch("joblib.load", return_value=mock_model), \
         patch("sys.modules", {"trading_platform.ai.lab.predictor": MagicMock()}):
        
        # Set up Path mocking for model exists
        mock_model_path = MagicMock()
        mock_model_path.exists.return_value = True
        mock_path_class.return_value = mock_model_path
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        
        # Should load successfully but generate no insights due to no trades
        assert engine.model_insights == []


def test_dse_model_insights_features_fallback():
    """Test feature extraction fallback when model has no features and no trades - covers lines 97-102."""
    analysis_data: dict[str, list[dict[str, float]]] = {}  # No trades key at all

    mock_model = MagicMock()
    # Model has no feature_names_in_ attribute
    del mock_model.feature_names_in_

    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("pathlib.Path") as mock_path_class, \
         patch("joblib.load", return_value=mock_model), \
         patch("sys.modules", {"trading_platform.ai.lab.predictor": MagicMock()}):
        
        # Set up Path mocking
        mock_model_path = MagicMock()
        mock_model_path.exists.return_value = True
        mock_path_class.return_value = mock_model_path
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        
        # Should handle the case where no trades exist
        assert engine.model_insights == []


def test_dse_generate_report_markdown_with_suggested_parameters():
    """Test markdown report generation with suggested parameters - covers lines 137-140."""
    analysis_data = {"some_data": 123}
    
    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]), \
         patch("trading_platform.ai.lab.param_suggester.suggest_parameters", 
               return_value={"param1": "value1", "param2": "value2"}):
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        report = engine.generate_report_markdown()
        
        # Should include suggested parameters section
        assert "## Suggested Parameters" in report
        assert "- param1: value1" in report  
        assert "- param2: value2" in report


def test_dse_generate_report_markdown_with_model_insights():
    """Test markdown report generation with model insights - covers lines 155-166."""
    analysis_data = {"some_data": 123}
    
    # Create mock model insights
    mock_insights = [{
        "trade_id": "trade123",
        "insight": {
            "predicted_profitable": True,
            "predicted_probability": 0.85,
            "feature_importances": {"feature1": 0.6, "feature2": 0.4}
        }
    }]
    
    with patch("trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.model_insights = mock_insights
        
        report = engine.generate_report_markdown()
        
        # Should include model insights section
        assert "## Model Insights" in report
        assert "### Trade ID: trade123" in report
        assert "- Predicted Profitable: True" in report
        assert "- Predicted Probability: 0.85" in report
        assert "- Feature Importances:" in report
        assert "    - feature1: 0.6" in report
        assert "    - feature2: 0.4" in report


def test_dse_generate_report_markdown_complex_evidence():
    """Test markdown report with complex evidence types - covers lines 190-192."""
    analysis_data = {"some_data": 123}
    
    # Create conclusion with complex evidence (non-scalar types)
    complex_evidence = {
        "simple_metric": 0.5,
        "complex_data": {"nested": {"values": [1, 2, 3]}, "list": ["a", "b"]},
        "another_list": [{"item1": "value1"}, {"item2": "value2"}]
    }
    conc = MockDiagnosticConclusion("Complex Issue", "Summary", complex_evidence)
    
    with patch("trading_platform.ai.synthesis.engine.get_all_rules", 
               return_value=[MockRule(conclusion_to_return=conc)]):
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()
        
        # Should include both scalar and complex evidence
        assert "- simple_metric: 0.5" in report
        assert "- complex_data:" in report
        assert "```json" in report
        assert '"nested"' in report  # JSON formatted complex data
        assert "- another_list:" in report


def test_dse_generate_report_markdown_non_dict_evidence():
    """Test markdown report with non-dict evidence - covers lines 223-224."""
    analysis_data = {"some_data": 123}
    
    # Create conclusion with non-dict evidence
    conc = MockDiagnosticConclusion("Issue", "Summary", ["item1", "item2", "item3"])
    
    with patch("trading_platform.ai.synthesis.engine.get_all_rules",
               return_value=[MockRule(conclusion_to_return=conc)]):
        
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()
        
        # Should format non-dict evidence as JSON
        assert "```json" in report
        assert '"item1"' in report
        assert '"item2"' in report
        assert '"item3"' in report
