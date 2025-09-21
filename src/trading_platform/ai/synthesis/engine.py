"""
This module defines the Diagnostic Synthesis Engine.
"""

import json
from typing import Any, Dict, List

from trading_platform.ai.synthesis.rules import DiagnosticConclusion, get_all_rules


class DiagnosticSynthesisEngine:
    """
    Consumes analysis data, runs a set of diagnostic rules, and synthesizes
    the findings into a human-readable and machine-readable report.
    """

    def __init__(self, analysis_data: Dict[str, Any]):
        """
        Initializes the engine with all the data required for analysis.

        Args:
            analysis_data: A dictionary containing all data for analysis, e.g.,
                           backtest metrics, model evaluation results, SHAP values, etc.
        """
        self.analysis_data = analysis_data
        self.rules = get_all_rules()
        self.conclusions: List[DiagnosticConclusion] = []

    def run(self) -> None:
        """Executes all diagnostic rules and stores the conclusions."""
        print("--- Running Diagnostic Synthesis Engine ---")
        for rule in self.rules:
            print(f"Evaluating rule: {rule.__class__.__name__}...")
            conclusion = rule.evaluate(self.analysis_data)
            if conclusion:
                self.conclusions.append(conclusion)
                print(f"  -> Conclusion found: {conclusion.title}")
        print("--- Engine run complete. ---")

    def generate_report_markdown(self) -> str:
        """Generates a human-readable Markdown report of the findings."""
        if not self.conclusions:
            return (
                "# AI Diagnostic Report\n\nNo specific issues were "
                "detected by the diagnostic rules."
            )

        report_parts = ["# AI Diagnostic Report\n"]
        for conc in self.conclusions:
            report_parts.append(f"## {conc.title}")
            report_parts.append(f"{conc.summary}\n")
            report_parts.append("**Evidence:**")
            evidence_json = json.dumps(conc.evidence, indent=2)
            report_parts.append(f"```json\n{evidence_json}\n```")

        return "\n".join(report_parts)

    def generate_report_json(self) -> str:
        """Generates a machine-readable JSON report of the findings."""
        return json.dumps([conc.to_dict() for conc in self.conclusions], indent=2)


if __name__ == "__main__":
    # Example Usage
    # This demonstrates how the engine would be used after a training/evaluation run.

    # 1. Create dummy analysis data
    dummy_data = {
        "backtest_metrics": {"n_trades": 650, "win_rate": 0.51, "sharpe_ratio": -0.2},
        "model_analysis": {"avg_pnl_left_on_table_at_tp": 15.50},
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
