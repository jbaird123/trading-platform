import json
import logging
from typing import Any, Dict

from trading_platform.ai.synthesis.recommendations import (
    generate_recommendations,
)
from trading_platform.ai.synthesis.rules import (
    get_all_rules,
)

logger = logging.getLogger(__name__)


class DiagnosticSynthesisEngine:
    # conclusions and recommendations are instance variables, not class variables
    def generate_recommendations(self) -> list[dict]:
        """
        Generates recommendations in the format required by `brief.json`.
        Each recommendation is derived from a diagnostic conclusion and
        mapped to the schema fields.
        """
        recommendations = []
        for conc in self.conclusions:
            # Map DiagnosticConclusion to recommendation schema
            recommendations.append(
                {
                    "id": conc.title.lower().replace(" ", "_"),
                    "title": conc.title,
                    "description": conc.summary,
                    # Placeholder: could be rule class name
                    "rule": conc.title,
                    # Default; can be set by rules in future
                    "severity": "info",
                    "suggested_action": None,
                }
            )
        return recommendations

    """
    Consumes analysis data, runs a set of diagnostic rules, and synthesizes
    the findings into a human-readable and machine-readable report.
    """

    def __init__(self, analysis_data: Dict[str, Any]):
        """
        Initializes the engine with all the data required for analysis.

        Args:
            analysis_data: A dictionary containing all data for analysis,
                e.g., backtest metrics, model evaluation results, SHAP values, etc.
        """
        self.analysis_data = analysis_data
        self.rules = get_all_rules()
        self.conclusions = []  # type: list[Any]
        self.recommendations = []  # type: list[Any]

    def run(self) -> None:
        """Executes all diagnostic rules and stores the conclusions."""
        logger.info("--- Running Diagnostic Synthesis Engine ---")
        for rule in self.rules:
            logger.info(f"Evaluating rule: {rule.__class__.__name__}...")
            conclusion = rule.evaluate(self.analysis_data)
            if conclusion:
                self.conclusions.append(conclusion)
                logger.info("  -> Conclusion found: %s", conclusion.title)
        # Generate recommendations from conclusions
        self.recommendations = generate_recommendations(self.conclusions)
        logger.info("--- Engine run complete. ---")

    def generate_report_markdown(self) -> str:
        """
        Generates a human-readable Markdown report of the findings.
        """
        report_parts = ["# AI Diagnostic Report\n"]

        # Recommendations at the top (actionable first)
        if self.recommendations:
            report_parts.append("## Recommendations\n")
            for rec in self.recommendations:
                report_parts.append(f"### {rec.title}")
                report_parts.append(f"{rec.summary}")
                report_parts.append("")
                report_parts.append(f"- Category: {rec.category}")
                report_parts.append(f"- Confidence: {rec.confidence}")
                report_parts.append("")

        # Conclusions with structured evidence
        if not self.conclusions:
            report_parts.append(
                "No specific issues were detected by the diagnostic rules."
            )
        else:
            for conc in self.conclusions:
                report_parts.append(f"## {conc.title}")
                report_parts.append(f"{conc.summary}\n")
                report_parts.append("**Evidence:**")
                # Render evidence as a bulleted list for readability.
                if isinstance(conc.evidence, dict) and conc.evidence:
                    for key, value in conc.evidence.items():
                        # Simple scalar types inline, complex types as JSON block
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            report_parts.append(f"- {key}: {value}")
                        else:
                            report_parts.append(f"- {key}:")
                            report_parts.append("")
                            report_parts.append(
                                f"```json\n{json.dumps(value, indent=2)}\n```"
                            )
                else:
                    # Fallback to JSON if evidence is not a dict
                    evidence_json = json.dumps(conc.evidence, indent=2)
                    report_parts.append(f"```json\n{evidence_json}\n```")
        return "\n".join(report_parts)

    def generate_report_json(self) -> str:
        """
        Generates a machine-readable JSON report of the findings,
        including recommendations.
        """
        return json.dumps(
            {
                "conclusions": [conc.to_dict() for conc in self.conclusions],
                "recommendations": [rec.__dict__ for rec in self.recommendations],
            },
            indent=2,
        )


if __name__ == "__main__":
    # Example Usage
    # This demonstrates how the engine would be used after a training/
    # evaluation run.

    # 1. Create dummy analysis data
    dummy_data = {
        "backtest_metrics": {
            "n_trades": 650,
            "win_rate": 0.51,
            "sharpe_ratio": -0.2,
        },
        "model_analysis": {
            "avg_pnl_left_on_table_at_tp": 15.50,
        },
    }

    # 2. Initialize and run the engine
    engine = DiagnosticSynthesisEngine(analysis_data=dummy_data)
    engine.run()

    # 3. Generate reports
    markdown_report = engine.generate_report_markdown()
    json_report = engine.generate_report_json()

    print("\n--- MARKDOWN REPORT ---")
    print(markdown_report)

    print("\n--- JSON REPORT ---")
    print(json_report)

    # Save reports to files
    with open("diagnostic_report.md", "w") as f:
        f.write(markdown_report)
    with open("diagnostic_report.json", "w") as f:
        f.write(json_report)
