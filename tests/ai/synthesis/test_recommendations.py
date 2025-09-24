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
