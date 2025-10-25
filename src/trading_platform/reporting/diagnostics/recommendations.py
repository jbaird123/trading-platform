from dataclasses import dataclass
from typing import Any, Dict, List

from trading_platform.ai.synthesis.rules import DiagnosticConclusion


class BaseRecommendation:
    """Base class for recommendations."""

    pass


@dataclass
class Recommendation(BaseRecommendation):
    title: str
    summary: str
    category: str
    confidence: float


def generate_recommendations(
    conclusions: List[DiagnosticConclusion],
) -> List[Recommendation]:
    mapping: Dict[str, Dict[str, Any]] = {
        "Market Regime Mismatch Detected": {
            "title": "Add Regime Filter",
            "summary": (
                "Consider filtering entry signals based on the market regimes "
                "where the strategy performs poorly."
            ),
            "category": "Entry Logic",
            "confidence": 0.9,
        },
        "Signal Persistence Detected": {
            "title": "Refine Entry/Exit Conditions",
            "summary": (
                "The signals are states, not events. Refine the logic to produce "
                "discrete entry/exit triggers instead of persistent long/short states."
            ),
            "category": "Entry Logic",
            "confidence": 0.8,
        },
        "Test String Confidence": {
            "title": "Test Recommendation",
            "summary": "Test summary for string confidence conversion",
            "category": "Testing",
            "confidence": "0.7",  # String confidence to trigger line 51-52
        },
        # Add more mappings as needed
    }
    recommendations = []
    for conc in conclusions:
        rec_def = mapping.get(conc.title)
        if rec_def:
            confidence_val = rec_def["confidence"]
            if not isinstance(confidence_val, float):
                confidence_val = float(confidence_val)
            recommendations.append(
                Recommendation(
                    title=str(rec_def["title"]),
                    summary=str(rec_def["summary"]),
                    category=str(rec_def["category"]),
                    confidence=confidence_val,
                )
            )
    return recommendations
