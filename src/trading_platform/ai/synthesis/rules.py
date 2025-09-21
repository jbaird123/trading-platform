"""
This module defines the rule-based system for the Diagnostic Synthesis Engine.
Each rule checks for a specific, potential strategy flaw.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DiagnosticConclusion:
    """A data class to hold the findings of a diagnostic rule."""

    def __init__(self, title: str, summary: str, evidence: Dict[str, Any]):
        self.title = title
        self.summary = summary
        self.evidence = evidence

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "summary": self.summary, "evidence": self.evidence}


class BaseDiagnosticRule(ABC):
    """Abstract base class for a diagnostic rule."""

    @abstractmethod
    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        """
        Evaluate the analysis data and return a conclusion if the rule is triggered.

        Args:
            analysis_data: A dictionary containing all data for analysis, e.g.,
                           backtest metrics, model evaluation results, SHAP values, etc.

        Returns:
            A DiagnosticConclusion object if the rule's conditions are met,
            otherwise None.
        """
        pass


class OverTradingRule(BaseDiagnosticRule):
    """Checks for signs of over-trading (high trade count with low profitability)."""

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        metrics = analysis_data.get("backtest_metrics", {})
        n_trades = metrics.get("n_trades", 0)
        win_rate = metrics.get("win_rate", 0.5)

        # Example thresholds (these should be configurable)
        if n_trades > 500 and win_rate < 0.55:
            summary = (
                "The strategy executed an unusually high number of trades "
                f"({n_trades}) "
                f"with a low win rate ({win_rate:.2%}), suggesting that the entry "
                "signals may be too frequent and not selective enough."
            )
            return DiagnosticConclusion(
                title="Potential Over-Trading Detected",
                summary=summary,
                evidence={
                    "n_trades": n_trades,
                    "win_rate": win_rate,
                    "thresholds": {"n_trades": 500, "win_rate": 0.55},
                },
            )
        return None


class InefficientExitsRule(BaseDiagnosticRule):
    """
    Placeholder rule to check if exits are systematically inefficient.
    This would consume model predictions about post-exit price movement.
    """

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        model_analysis = analysis_data.get("model_analysis", {})
        # Example: Data from a model trained to predict profit left on the table
        avg_pnl_left_on_table = model_analysis.get("avg_pnl_left_on_table_at_tp", 0)

        if avg_pnl_left_on_table > 10.0:  # Example threshold
            summary = (
                f"The model indicates that, on average, ${avg_pnl_left_on_table:.2f} "
                "of potential profit was left on the table when trades exited via "
                "take-profit. This suggests the take-profit level may be too tight."
            )
            return DiagnosticConclusion(
                title="Inefficient Take-Profit Exits Detected",
                summary=summary,
                evidence={
                    "avg_pnl_left_on_table_at_tp": avg_pnl_left_on_table,
                    "threshold": 10.0,
                },
            )
        return None


def get_all_rules() -> List[BaseDiagnosticRule]:
    """Returns a list of all diagnostic rules to be executed."""
    return [OverTradingRule(), InefficientExitsRule()]
