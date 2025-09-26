from unittest.mock import Mock

from trading_platform.ai.synthesis.recommendations import generate_recommendations
from trading_platform.ai.synthesis.rules import DiagnosticConclusion


def test_generate_recommendations_signal_persistence():
    conc = DiagnosticConclusion(
        title="Signal Persistence Detected",
        summary="Signals were persistent 85% of the time.",
        evidence={"signal_persistence_pct": 0.85},
    )
    recs = generate_recommendations([conc])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.title == "Refine Entry/Exit Conditions"
    assert rec.category == "Entry Logic"
    assert rec.confidence == 0.8
    assert "discrete entry/exit triggers" in rec.summary


def test_generate_recommendations_market_regime_mismatch():
    conc = DiagnosticConclusion(
        title="Market Regime Mismatch Detected",
        summary="Strategy performed poorly in ranging regimes.",
        evidence={"regime": "ranging"},
    )
    recs = generate_recommendations([conc])
    assert len(recs) == 1
    rec = recs[0]
    assert rec.title == "Add Regime Filter"
    assert rec.category == "Entry Logic"
    assert rec.confidence == 0.9
    assert "filtering entry signals" in rec.summary


def test_generate_recommendations_no_match():
    conc = DiagnosticConclusion(
        title="Unrelated Issue", summary="Some other issue.", evidence={}
    )
    recs = generate_recommendations([conc])
    assert recs == []


# --- Consolidated from tests/ai/test_synthesis_recommendations_coverage_gaps.py ---


def test_confidence_string_conversion() -> None:
    mock_conclusion = Mock()
    mock_conclusion.title = "Test String Confidence"
    recs = generate_recommendations([mock_conclusion])
    assert len(recs) == 1
    assert recs[0].confidence == 0.7
    assert recs[0].title == "Test Recommendation"


def test_confidence_already_float() -> None:
    mock_conclusion = Mock()
    mock_conclusion.title = "Market Regime Mismatch Detected"
    recs = generate_recommendations([mock_conclusion])
    assert len(recs) == 1
    assert isinstance(recs[0].confidence, float)


def test_empty_conclusions_list() -> None:
    assert generate_recommendations([]) == []


def test_no_matching_mapping() -> None:
    mock_conclusion = Mock()
    mock_conclusion.title = "Non-existent Title"
    assert generate_recommendations([mock_conclusion]) == []
