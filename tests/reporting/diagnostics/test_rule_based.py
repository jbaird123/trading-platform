"""Tests for RuleBasedAnalyzer - Heuristic diagnostic analysis.

Tests for the migrated RuleBasedAnalyzer implementation (from
DiagnosticSynthesisEngine).
"""

import json

import pytest
from trading_platform.reporting.diagnostics import RuleBasedAnalyzer


@pytest.fixture
def sample_analysis_data():
    """Create sample analysis data for testing."""
    return {
        "backtest_metrics": {
            "n_trades": 100,
            "win_rate": 0.55,
            "sharpe_ratio": 1.2,
            "total_pnl": 1500.0,
        },
        "trades": [
            {
                "id": 1,
                "pnl": 10.0,
                "entry_context": {"rsi": 30.0, "ema_fast": 1.05},
                "mfe_currency": 15.0,
                "mae_currency": 5.0,
            },
            {
                "id": 2,
                "pnl": -5.0,
                "entry_context": {"rsi": 70.0, "ema_fast": 1.10},
                "mfe_currency": 2.0,
                "mae_currency": 8.0,
            },
        ],
        "model_analysis": {
            "avg_pnl_left_on_table_at_tp": 5.0,
        },
    }


class TestRuleBasedAnalyzer:
    """Test suite for RuleBasedAnalyzer."""

    def test_initialization(self, sample_analysis_data):
        """Verify analyzer can be instantiated with analysis data."""
        analyzer = RuleBasedAnalyzer(analysis_data=sample_analysis_data)
        assert analyzer is not None
        assert analyzer.analysis_data == sample_analysis_data
        assert analyzer.conclusions == []
        assert analyzer.recommendations == []

    def test_run_executes_rules(self, sample_analysis_data):
        """Verify run() executes all rules."""
        analyzer = RuleBasedAnalyzer(analysis_data=sample_analysis_data)
        analyzer.run()

        # Verify rules were executed (conclusions may or may not be generated)
        assert isinstance(analyzer.conclusions, list)
        assert isinstance(analyzer.recommendations, list)

    def test_generate_report_markdown(self, sample_analysis_data):
        """Verify generate_report_markdown() returns string."""
        analyzer = RuleBasedAnalyzer(analysis_data=sample_analysis_data)
        analyzer.run()

        report = analyzer.generate_report_markdown()
        assert isinstance(report, str)
        assert "# AI Diagnostic Report" in report

    def test_generate_report_json(self, sample_analysis_data):
        """Verify generate_report_json() returns valid JSON."""
        analyzer = RuleBasedAnalyzer(analysis_data=sample_analysis_data)
        analyzer.run()

        report_json = analyzer.generate_report_json()
        assert isinstance(report_json, str)

        # Verify it's valid JSON
        report_data = json.loads(report_json)
        assert "conclusions" in report_data
        assert "recommendations" in report_data
        assert "model_insights" in report_data
        assert "suggested_parameters" in report_data

    def test_with_empty_analysis_data(self):
        """Verify analyzer handles empty analysis data."""
        analyzer = RuleBasedAnalyzer(analysis_data={})
        analyzer.run()

        # Should not crash, just produce empty/minimal report
        report = analyzer.generate_report_markdown()
        assert isinstance(report, str)
        assert "# AI Diagnostic Report" in report

    def test_generate_recommendations_format(self, sample_analysis_data):
        """Verify generate_recommendations() returns correct format."""
        analyzer = RuleBasedAnalyzer(analysis_data=sample_analysis_data)
        analyzer.run()

        recommendations = analyzer.generate_recommendations()
        assert isinstance(recommendations, list)

        # If there are recommendations, verify structure
        for rec in recommendations:
            assert "id" in rec
            assert "title" in rec
            assert "description" in rec
            assert "rule" in rec
            assert "severity" in rec

    def test_report_contains_sections(self, sample_analysis_data):
        """Verify markdown report contains expected sections."""
        analyzer = RuleBasedAnalyzer(analysis_data=sample_analysis_data)
        analyzer.run()

        report = analyzer.generate_report_markdown()

        # Report should have diagnostic header
        assert "# AI Diagnostic Report" in report

        # If there are no conclusions, should say so
        if len(analyzer.conclusions) == 0:
            assert "No specific issues were detected" in report
