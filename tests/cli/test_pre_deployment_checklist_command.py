from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_pre_deployment_checklist_requires_arguments() -> None:
    """Test that pre-deployment-checklist requires all arguments."""
    result = subprocess.run(
        ["poetry", "run", "tp", "pre-deployment-checklist"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    # Should mention required arguments
    assert "required" in result.stderr.lower() or "--" in result.stderr


def test_pre_deployment_checklist_prints_results(tmp_path: Path) -> None:
    """Test that pre-deployment-checklist prints results with checkboxes."""
    # Create mock files
    model_metrics_file = tmp_path / "model_metrics.json"
    model_metrics = {
        "profitability_r2": 0.3,
        "diagnostic_f1": 0.7,
    }
    model_metrics_file.write_text(json.dumps(model_metrics))

    walk_forward_file = tmp_path / "walk_forward_results.json"
    walk_forward_results = {
        "2020": {"sharpe_ratio": 1.5, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": 1.6, "max_drawdown": -0.12},
    }
    walk_forward_file.write_text(json.dumps(walk_forward_results))

    phase4_file = tmp_path / "phase4_results.json"
    phase4_results = {
        "without_filter": {"sharpe_ratio": 1.2},
        "with_filter_0.5": {"sharpe_ratio": 1.8},
    }
    phase4_file.write_text(json.dumps(phase4_results))

    strategy_file = tmp_path / "strategy.yaml"
    strategy_file.write_text("metadata:\n  git_commit: abc123\n")

    # Run command
    result = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "pre-deployment-checklist",
            "--model-metrics",
            str(model_metrics_file),
            "--walk-forward-results",
            str(walk_forward_file),
            "--phase4-results",
            str(phase4_file),
            "--strategy-config",
            str(strategy_file),
        ],
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr

    # Should print checklist
    assert "checklist" in output.lower() or "deployment" in output.lower()

    # Should return 0 for all passing
    assert result.returncode == 0


def test_pre_deployment_checklist_fails_when_criteria_not_met(tmp_path: Path) -> None:
    """Test that checklist fails when criteria are not met."""
    # Create mock files with failing criteria
    model_metrics_file = tmp_path / "model_metrics.json"
    model_metrics = {
        "profitability_r2": 0.1,  # Below threshold
        "diagnostic_f1": 0.5,  # Below threshold
    }
    model_metrics_file.write_text(json.dumps(model_metrics))

    walk_forward_file = tmp_path / "walk_forward_results.json"
    walk_forward_results = {
        "2020": {"sharpe_ratio": -0.5, "max_drawdown": -0.35},  # Negative
    }
    walk_forward_file.write_text(json.dumps(walk_forward_results))

    phase4_file = tmp_path / "phase4_results.json"
    phase4_results = {
        "without_filter": {"sharpe_ratio": 1.2},
        "with_filter_0.5": {"sharpe_ratio": 1.2},  # No improvement
    }
    phase4_file.write_text(json.dumps(phase4_results))

    strategy_file = tmp_path / "strategy.yaml"
    strategy_file.write_text("metadata: {}\n")  # No git commit

    # Run command
    result = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "pre-deployment-checklist",
            "--model-metrics",
            str(model_metrics_file),
            "--walk-forward-results",
            str(walk_forward_file),
            "--phase4-results",
            str(phase4_file),
            "--strategy-config",
            str(strategy_file),
        ],
        capture_output=True,
        text=True,
    )

    # Should return non-zero when checks fail
    assert result.returncode == 1
