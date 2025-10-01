from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


# DiagnosticConclusion class (restored)
class DiagnosticConclusion:
    """A data class to hold the findings of a diagnostic rule."""

    def __init__(self, title: str, summary: str, evidence: Dict[str, Any]):
        self.title = title
        self.summary = summary
        self.evidence = evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "evidence": self.evidence,
        }


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


class InefficientExitsRule(BaseDiagnosticRule):
    """
    Placeholder rule to check if exits are systematically inefficient.
    This would consume model predictions about post-exit price movement.
    """

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        model_analysis = analysis_data.get("model_analysis", {})
        trades = analysis_data.get("trades", [])
        threshold = 10.0
        conclusions = []

        # Model analysis branch
        avg_pnl_left = model_analysis.get("avg_pnl_left_on_table_at_tp")
        if avg_pnl_left is not None and avg_pnl_left > threshold:
            summary = (
                f"${avg_pnl_left:.2f} of potential profit was left on the table "
                "by take-profit exits, "
                "suggesting inefficient exit logic."
            )
            conclusions.append(
                DiagnosticConclusion(
                    title="Inefficient Take-Profit Exits Detected",
                    summary=summary,
                    evidence={
                        "avg_pnl_left_on_table_at_tp": avg_pnl_left,
                        "threshold": threshold,
                    },
                )
            )

        # Trades analysis branch
        if trades:
            high_mfe_trades = [
                t
                for t in trades
                if t.get("mfe_currency") is not None
                and t.get("mfe_currency") > threshold
            ]
            high_mae_trades = [
                t
                for t in trades
                if t.get("mae_currency") is not None
                and t.get("mae_currency") > threshold
            ]
            if high_mfe_trades or high_mae_trades:
                summary = (
                    f"{len(high_mfe_trades)} trades had MFE > ${threshold}, "
                    f"{len(high_mae_trades)} trades had MAE > ${threshold}. "
                    "This suggests exits may be inefficient."
                )
                conclusions.append(
                    DiagnosticConclusion(
                        title="Inefficient Exits Detected (Trade Analysis)",
                        summary=summary,
                        evidence={
                            "high_mfe_trades": len(high_mfe_trades),
                            "high_mae_trades": len(high_mae_trades),
                            "threshold": threshold,
                        },
                    )
                )

        if not conclusions:
            return None
        # Merge all conclusions into one
        merged_title = "; ".join(c.title for c in conclusions)
        merged_summary = "\n".join(c.summary for c in conclusions)
        merged_evidence = {}
        for c in conclusions:
            merged_evidence.update(c.evidence)
        return DiagnosticConclusion(
            title=merged_title,
            summary=merged_summary,
            evidence=merged_evidence,
        )


# --- LowWinRateHighTradesRule ---
class LowWinRateHighTradesRule(BaseDiagnosticRule):
    """
    Triggers if win_rate is below a configurable threshold AND n_trades is above a
    configurable threshold (even if n_trades is not unusually high like 500).
    """

    def __init__(self, win_rate_threshold: float = 0.55, n_trades_threshold: int = 100):
        self.win_rate_threshold = win_rate_threshold
        self.n_trades_threshold = n_trades_threshold

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        metrics = analysis_data.get("backtest_metrics", {})
        if "n_trades" not in metrics or "win_rate" not in metrics:
            return None
        n_trades = metrics["n_trades"]
        win_rate = metrics["win_rate"]
        if n_trades > self.n_trades_threshold and win_rate < self.win_rate_threshold:
            summary = (
                f"The strategy executed {n_trades} trades with a low win rate "
                f"({win_rate:.2%}). "
                "This may indicate excessive trading or poor signal quality."
            )
            return DiagnosticConclusion(
                title="Low Win Rate with High Trade Count",
                summary=summary,
                evidence={
                    "n_trades": n_trades,
                    "win_rate": win_rate,
                    "thresholds": {
                        "n_trades": self.n_trades_threshold,
                        "win_rate": self.win_rate_threshold,
                    },
                },
            )
        return None


# --- StrategyParameterOptimizationOpportunityRule ---
class StrategyParameterOptimizationOpportunityRule(BaseDiagnosticRule):
    """
    Checks if key strategy parameters (e.g., fast, slow for EMA crossover) are null
    or default values in brief.json.strategy_params, suggesting they haven't been
    optimized.
    """

    def __init__(self):
        pass

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        params = analysis_data.get("strategy_params", {})
        if not params:
            return None
        none_params = {k: v for k, v in params.items() if v is None}
        if none_params:
            summary = (
                "The following strategy parameters are unset (None): "
                f"{none_params}. Consider running parameter search."
            )
            return DiagnosticConclusion(
                title="Strategy Parameter Optimization Opportunity",
                summary=summary,
                evidence={"none_params": none_params},
            )
        return None


# --- SignalPersistenceRule ---
class SignalPersistenceRule(BaseDiagnosticRule):
    """
    Analyzes signal_quality_analysis data to detect if signals are persistent
    states rather than discrete events.
    """

    def __init__(self, persistence_threshold: float = 0.8):
        self.persistence_threshold = persistence_threshold

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        sq = analysis_data.get("signal_quality_analysis", {})
        persistence_pct = sq.get("signal_persistence_pct")
        if persistence_pct is not None and persistence_pct > self.persistence_threshold:
            summary = (
                f"Signals are persistent {persistence_pct:.1f}% of the time, "
                "suggesting they may be states, not events. Consider reviewing "
                "signal logic."
            )
            return DiagnosticConclusion(
                title="Signal Persistence Detected",
                summary=summary,
                evidence={
                    "signal_persistence_pct": persistence_pct,
                    "threshold": self.persistence_threshold,
                },
            )
        return None


# --- MarketRegimeMismatchRule ---
class MarketRegimeMismatchRule(BaseDiagnosticRule):
    """
    Identifies if the strategy performed poorly in specific market regimes
    using brief.json.regimes data. Triggers if any regime has a win rate below
    a threshold and sufficient trades.
    """

    def __init__(self, win_rate_threshold: float = 0.45, min_trades: int = 20):
        self.win_rate_threshold = win_rate_threshold
        self.min_trades = min_trades

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        regimes = analysis_data.get("regimes", {})
        if not regimes:
            return None
        mismatches = {}
        for regime, stats in regimes.items():
            n_trades = stats.get("n_trades", 0)
            win_rate = stats.get("win_rate")
            if (
                n_trades >= self.min_trades
                and win_rate is not None
                and win_rate < self.win_rate_threshold
            ):
                mismatches[regime] = {
                    "n_trades": n_trades,
                    "win_rate": win_rate,
                }
        if mismatches:
            summary = (
                "Strategy underperformed in the following market regimes: "
                f"{mismatches}. Consider regime-specific tuning."
            )
            return DiagnosticConclusion(
                title="Market Regime Mismatch Detected",
                summary=summary,
                evidence={"regime_mismatches": mismatches},
            )
        return None


# --- DataQualityImpactRule ---
class DataQualityImpactRule(BaseDiagnosticRule):
    """
    Flags significant data quality issues in brief.json.data_quality and
    correlates them with poor performance.
    """

    def __init__(self, quality_threshold: float = 0.8, perf_threshold: float = 0.0):
        self.quality_threshold = quality_threshold
        self.perf_threshold = perf_threshold

    def evaluate(self, analysis_data: Dict[str, Any]) -> Optional[DiagnosticConclusion]:
        dq = analysis_data.get("data_quality", {})
        perf = analysis_data.get("backtest_metrics", {})
        # Assume data_quality has a 'quality_score' (0-1, 1=perfect)
        quality_score = dq.get("quality_score")
        win_rate = perf.get("win_rate")
        if (
            quality_score is not None
            and quality_score < self.quality_threshold
            and win_rate is not None
            and win_rate <= self.perf_threshold
        ):
            summary = (
                f"Data quality score is low ({quality_score:.2f}) and win rate is "
                f"also low ({win_rate:.2%}). Poor data quality may be impacting "
                "performance."
            )
            return DiagnosticConclusion(
                title="Data Quality Impact Detected",
                summary=summary,
                evidence={
                    "quality_score": quality_score,
                    "win_rate": win_rate,
                    "thresholds": {
                        "quality_score": self.quality_threshold,
                        "win_rate": self.perf_threshold,
                    },
                },
            )
        return None


# --- get_all_rules ---
def get_all_rules() -> list[BaseDiagnosticRule]:
    return [
        InefficientExitsRule(),
        LowWinRateHighTradesRule(),
        StrategyParameterOptimizationOpportunityRule(),
        SignalPersistenceRule(),
        MarketRegimeMismatchRule(),
        DataQualityImpactRule(),
        # Add other rules here
    ]
