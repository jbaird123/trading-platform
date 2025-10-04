"""AI synthesis engine tests.

# Validates: [AI-10.6.1]
"""

import json
import logging
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine
from trading_platform.ai.synthesis.recommendations import Recommendation
from trading_platform.ai.synthesis.rules import (
    DiagnosticConclusion,  # Import actual class for type hinting
)
from trading_platform.core import paths


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

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch(
        "trading_platform.ai.lab.param_suggester.suggest_parameters",
        side_effect=ImportError("Module not found"),
    ), patch("trading_platform.ai.synthesis.engine.logger.warning") as mock_warning:
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should handle the exception and log a warning
        mock_warning.assert_called_with(
            "Failed to suggest parameters: Module not found"
        )
        assert engine.suggested_parameters == {}


def test_dse_model_insights_no_run_dir():
    """Test model insights when run directory doesn't exist - covers lines 78-80."""
    analysis_data = {
        "meta": {"run_id": "test123"},
        "_brief_path": "/nonexistent/path",
        "trades": [],
    }

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path") as mock_path_class:
        # Set up Path mocking for non-existent run dir
        mock_run_dir = MagicMock()
        mock_run_dir.exists.return_value = False  # Run dir doesn't exist
        mock_model_path = MagicMock()
        mock_model_path.exists.return_value = False  # Model doesn't exist either

        def path_side_effect(x):
            if x == "/nonexistent/path":
                return mock_run_dir
            # This now correctly checks the new default path
            if x == paths.ARTIFACTS_DIR / "profitability_model.joblib":
                return mock_model_path
            return MagicMock(exists=lambda: False)

        mock_path_class.side_effect = path_side_effect

        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should not generate any model insights
        assert engine.model_insights == []


def test_dse_model_insights_no_model_file():
    """Test when model file doesn't exist - covers line 87."""
    analysis_data: dict[str, list[dict[str, float]]] = {"trades": []}

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=False):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should not generate any model insights
        assert engine.model_insights == []


def test_dse_model_insights_run_dir_exists():
    """Test model insights when run directory exists - covers lines 84-86."""
    analysis_data = {"meta": {"run_id": "test123"}, "_brief_path": "/tmp/test_run"}

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path") as mock_path_class, patch(
        "joblib.load", side_effect=Exception("Skip actual loading")
    ):
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

        # Constructor attempts to load model (fails due to mocked exception)
        # This covers lines 84-86 where candidate path is set and checked
        assert engine.model_insights == []


def test_dse_model_insights_successful_load_no_trades():
    """Test model loading success but no trades to process - covers lines 93-107."""
    analysis_data: dict[str, list[dict[str, float]]] = {"trades": []}  # Empty

    # Mock the model loading to succeed but avoid the complex dependencies
    mock_model = MagicMock()
    mock_model.feature_names_in_ = ["feature1", "feature2"]

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", return_value=mock_model
    ), patch("sys.modules", {"trading_platform.ai.lab.predictor": MagicMock()}):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should load successfully but generate no insights due to no trades
        assert engine.model_insights == []


def test_dse_model_insights_features_fallback():
    """Test feature extraction fallback with no features/trades - covers 97-102."""
    analysis_data: dict[str, list[dict[str, float]]] = {}  # No trades key at all

    mock_model = MagicMock()
    # Model has no feature_names_in_ attribute
    del mock_model.feature_names_in_

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", return_value=mock_model
    ), patch("sys.modules", {"trading_platform.ai.lab.predictor": MagicMock()}):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should handle the case where no trades exist
        assert engine.model_insights == []


def test_dse_generate_report_markdown_with_suggested_parameters():
    """Test markdown report with suggested parameters - covers lines 137-140."""
    analysis_data = {"some_data": 123}

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch(
        "trading_platform.ai.lab.param_suggester.suggest_parameters",
        return_value={"param1": "value1", "param2": "value2"},
    ):
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
    mock_insights = [
        {
            "trade_id": "trade123",
            "insight": {
                "predicted_profitable": True,
                "predicted_probability": 0.85,
                "feature_importances": {"feature1": 0.6, "feature2": 0.4},
            },
        }
    ]

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
        "another_list": [{"item1": "value1"}, {"item2": "value2"}],
    }
    conc = MockDiagnosticConclusion("Complex Issue", "Summary", complex_evidence)

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ):
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

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules",
        return_value=[MockRule(conclusion_to_return=conc)],
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        engine.run()
        report = engine.generate_report_markdown()

        # Should format non-dict evidence as JSON
        assert "```json" in report
        assert '"item1"' in report
        assert '"item2"' in report
        assert '"item3"' in report


def test_dse_model_insights_with_trades_and_features():
    """Test model insights generation with trades - covers lines 98-100, 106-107."""
    analysis_data = {
        "trades": [
            {
                "id": "trade1",
                "entry_context": {"feature1": 1.0, "feature2": 2.0},
            },
            {
                "id": "trade2",
                "entry_context": {"feature1": 1.5, "feature2": 2.5},
            },
        ]
    }

    # Mock model with feature_names_in_ set to None (to trigger fallback)
    mock_model = MagicMock()
    mock_model.feature_names_in_ = None

    # Mock trade insights function
    mock_insight_func = MagicMock()
    mock_insight_func.return_value = {
        "predicted_profitable": True,
        "predicted_probability": 0.8,
        "feature_importances": {"feature1": 0.6, "feature2": 0.4},
    }

    # Create a mock module that simulates the predictor module
    mock_predictor_module = MagicMock()
    mock_predictor_module.get_trade_insights = mock_insight_func

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", return_value=mock_model
    ), patch.dict(
        "sys.modules", {"trading_platform.ai.lab.predictor": mock_predictor_module}
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)
        # Should have model insights generated
        assert len(engine.model_insights) == 2
        assert engine.model_insights[0]["trade_id"] == "trade1"
        assert engine.model_insights[1]["trade_id"] == "trade2"

        # Verify get_trade_insights was called with sorted features (lines 98-100)
        expected_features = ["feature1", "feature2"]  # Sorted from entry_context
        mock_insight_func.assert_any_call(
            mock_model, analysis_data["trades"][0], expected_features
        )
        mock_insight_func.assert_any_call(
            mock_model, analysis_data["trades"][1], expected_features
        )


def test_dse_model_insights_with_feature_names_list():
    """Test model insights when features_any is a list - covers line 100."""
    analysis_data = {
        "trades": [
            {"id": "trade1", "entry_context": {"feature1": 1.0}},
        ]
    }

    # Mock model with feature_names_in_ as a list of non-string types
    mock_model = MagicMock()
    mock_model.feature_names_in_ = [123, 456, 789]  # Non-string features

    mock_insight_func = MagicMock()
    mock_insight_func.return_value = {"predicted_profitable": False}

    # Create a mock module that simulates the predictor module
    mock_predictor_module = MagicMock()
    mock_predictor_module.get_trade_insights = mock_insight_func

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", return_value=mock_model
    ), patch.dict(
        "sys.modules", {"trading_platform.ai.lab.predictor": mock_predictor_module}
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should convert non-string features (line 100: str(f) for f in features_any)
        expected_features = ["123", "456", "789"]
        mock_insight_func.assert_called_with(
            mock_model, analysis_data["trades"][0], expected_features
        )
        # Verify model insights were generated
        assert len(engine.model_insights) == 1


def test_dse_model_loading_exception_handling():
    """Test model loading exception handling - covers lines 112-113."""
    analysis_data = {"trades": [{"id": "trade1"}]}

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", side_effect=Exception("Model loading failed")
    ), patch("trading_platform.ai.synthesis.engine.logger.warning") as mock_warning:
        engine = DiagnosticSynthesisEngine(analysis_data)
        # Should handle exception and log warning (message may vary due to numpy issues)
        mock_warning.assert_called()
        assert "Failed to generate model insights:" in mock_warning.call_args[0][0]
        assert engine.model_insights == []


def test_main_block_execution():
    """Test the __main__ block execution - covers lines 223-252."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    # Get path to the engine module - fix the path calculation
    current_test_dir = Path(__file__).parent  # tests/ai/synthesis/
    repo_root = current_test_dir.parent.parent.parent  # Back to trading-platform root
    module_path = (
        repo_root / "src" / "trading_platform" / "ai" / "synthesis" / "engine.py"
    )

    # Set up environment to include src in PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    # Run the module as a script to execute the __main__ block
    result = subprocess.run(
        [sys.executable, str(module_path)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    # Check that it ran successfully
    assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"

    # Verify expected output patterns
    assert "--- MARKDOWN REPORT ---" in result.stdout
    assert "--- JSON REPORT ---" in result.stdout
    assert "AI Diagnostic Report" in result.stdout


def test_main_block_with_runpy():
    """Test the __main__ block using runpy for coverage tracking - lines 223-252."""
    import runpy
    import sys
    from pathlib import Path
    from unittest.mock import patch

    # Mock file operations to avoid actually writing files
    mock_open = patch("builtins.open", create=True)

    with mock_open, patch.object(sys, "argv", ["engine.py"]):
        # Fix the path calculation
        current_test_dir = Path(__file__).parent  # tests/ai/synthesis/
        repo_root = (
            current_test_dir.parent.parent.parent
        )  # Back to trading-platform root
        module_path = str(
            repo_root / "src" / "trading_platform" / "ai" / "synthesis" / "engine.py"
        )

        # This should execute the __main__ block and hit all the lines
        try:
            runpy.run_path(module_path, run_name="__main__")
        except SystemExit:
            pass  # Expected if script calls sys.exit


def test_dse_model_path_with_run_id_fallback():
    """Test model path fallback when run_dir doesn't exist - covers branch 85->87."""
    analysis_data = {
        "meta": {"run_id": "test123"},
        "_brief_path": "/nonexistent/path/brief.json",
        "trades": [{"id": "trade1", "entry_context": {"feature1": 1.0}}],
    }

    # Mock model that exists in current directory but not in run directory
    mock_model = MagicMock()
    mock_model.feature_names_in_ = ["feature1"]

    mock_insight_func = MagicMock()
    mock_insight_func.return_value = {"predicted_profitable": True}

    mock_predictor_module = MagicMock()
    mock_predictor_module.get_trade_insights = mock_insight_func

    def selective_exists(self):
        # The brief path from analysis_data doesn't exist
        if str(self) == "/nonexistent/path/brief.json":
            return False
        # The fallback model in the artifacts dir *does* exist
        if self == paths.ARTIFACTS_DIR / "profitability_model.joblib":
            return True
        # Default to false for any other path checks
        return False

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", new=selective_exists), patch(
        "joblib.load", return_value=mock_model
    ), patch.dict(
        "sys.modules", {"trading_platform.ai.lab.predictor": mock_predictor_module}
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should still generate model insights using fallback path
        assert len(engine.model_insights) == 1
        assert engine.model_insights[0]["trade_id"] == "trade1"


def test_dse_features_from_trades_empty_entry_context():
    """Test feature extraction when trades have empty entry_context - branch 99->104."""
    analysis_data = {
        "trades": [
            {"id": "trade1", "entry_context": {}},  # Empty entry_context
            {"id": "trade2"},  # No entry_context at all
        ]
    }

    # Mock model with feature_names_in_ set to None (to trigger fallback)
    mock_model = MagicMock()
    mock_model.feature_names_in_ = None

    mock_insight_func = MagicMock()
    mock_insight_func.return_value = {"predicted_profitable": True}

    mock_predictor_module = MagicMock()
    mock_predictor_module.get_trade_insights = mock_insight_func

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", return_value=mock_model
    ), patch.dict(
        "sys.modules", {"trading_platform.ai.lab.predictor": mock_predictor_module}
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should handle trades with no/empty entry_context gracefully
        # The first trade has empty entry_context, so features should be empty
        # This should trigger the branch 99->104 where trades is empty/no features
        assert len(engine.model_insights) == 2
        mock_insight_func.assert_any_call(mock_model, analysis_data["trades"][0], [])
        mock_insight_func.assert_any_call(mock_model, {"id": "trade2"}, [])


def test_dse_run_dir_exists_but_candidate_model_missing():
    """Test when run_dir exists but candidate model doesn't - branch 85->87."""
    analysis_data = {
        "meta": {"run_id": "test123"},
        "_brief_path": "/existing/path/brief.json",
        "trades": [],
    }

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path") as mock_path_class:

        def path_side_effect(path_str):
            mock_path = MagicMock()
            if path_str == "/existing/path/brief.json":
                # This is the run_dir - exists
                mock_path.exists.return_value = True
                # Mock the division operator for run_dir / "profitability_model.joblib"
                candidate_mock = MagicMock()
                candidate_mock.exists.return_value = (
                    False  # Candidate model doesn't exist
                )
                mock_path.__truediv__.return_value = candidate_mock
            elif "profitability_model.joblib" in str(path_str):
                # Fallback model path - also doesn't exist
                mock_path.exists.return_value = False
            else:
                mock_path.exists.return_value = False
            return mock_path

        mock_path_class.side_effect = path_side_effect

        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should not generate model insights since no model exists
        assert engine.model_insights == []


def test_dse_empty_trades_list():
    """Test when trades list is empty - covers branch 99->104."""
    analysis_data: dict = {
        "trades": []  # Empty list (not missing key)
    }

    mock_model = MagicMock()
    mock_model.feature_names_in_ = None  # This should trigger the trades branch

    mock_predictor_module = MagicMock()
    mock_predictor_module.get_trade_insights = MagicMock()

    with patch(
        "trading_platform.ai.synthesis.engine.get_all_rules", return_value=[]
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "joblib.load", return_value=mock_model
    ), patch.dict(
        "sys.modules", {"trading_platform.ai.lab.predictor": mock_predictor_module}
    ):
        engine = DiagnosticSynthesisEngine(analysis_data)

        # Should not generate model insights since trades list is empty
        # This should hit the branch where: if trades: (False) -> jump to line 104
        assert engine.model_insights == []
