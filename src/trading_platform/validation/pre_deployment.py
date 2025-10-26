from __future__ import annotations

from typing import Any


def check_model_baselines(
    metrics: dict[str, float], thresholds: dict[str, float]
) -> bool:
    """
    Check if model metrics meet minimum baselines.

    Args:
        metrics: Dict of metric names to values
        thresholds: Dict of metric names to minimum thresholds

    Returns:
        True if all metrics meet or exceed thresholds, False otherwise
    """
    for metric_name, threshold in thresholds.items():
        if metric_name not in metrics:
            return False
        if metrics[metric_name] < threshold:
            return False
    return True


def check_walk_forward_performance(results: dict[str, Any]) -> bool:
    """
    Check if walk-forward validation shows consistent positive performance.

    Args:
        results: Dict of period results with performance metrics

    Returns:
        True if all periods have positive Sharpe ratio, False otherwise
    """
    if not results:
        return False

    for period_metrics in results.values():
        sharpe = period_metrics.get("sharpe_ratio", 0)
        if sharpe <= 0:
            return False

    return True


def check_filter_threshold_justified(
    phase4_results: dict[str, Any], threshold: float
) -> tuple[bool, str]:
    """
    Check if predictive filter threshold is justified by Phase 4 results.

    Args:
        phase4_results: Dict with 'without_filter' and 'with_filter_X' results
        threshold: The filter threshold to check

    Returns:
        Tuple of (is_justified, justification_text)
    """
    without_filter = phase4_results.get("without_filter", {})
    with_filter_key = f"with_filter_{threshold}"
    with_filter = phase4_results.get(with_filter_key, {})

    if not without_filter or not with_filter:
        return (False, "Missing comparison data for filter threshold justification")

    sharpe_without = without_filter.get("sharpe_ratio", 0)
    sharpe_with = with_filter.get("sharpe_ratio", 0)

    improvement = sharpe_with - sharpe_without
    pct_improvement = (
        (improvement / abs(sharpe_without)) * 100 if sharpe_without != 0 else 0
    )

    if improvement > 0 and pct_improvement >= 10:
        message = (
            f"Filter threshold {threshold} shows {pct_improvement:.1f}% "
            f"improvement in Sharpe ratio ({sharpe_without:.2f} → {sharpe_with:.2f})"
        )
        return (True, message)
    else:
        message = (
            f"Filter threshold {threshold} shows insufficient improvement "
            f"({sharpe_without:.2f} → {sharpe_with:.2f}, {pct_improvement:.1f}%)"
        )
        return (False, message)


def check_git_commit_exists(config: dict[str, Any]) -> bool:
    """
    Check if git commit hash is recorded in strategy config.

    Args:
        config: Strategy configuration dict

    Returns:
        True if git_commit exists in metadata, False otherwise
    """
    metadata = config.get("metadata", {})
    return "git_commit" in metadata and bool(metadata["git_commit"])


def run_pre_deployment_checklist(
    model_metrics: dict[str, float],
    walk_forward_results: dict[str, Any],
    phase4_results: dict[str, Any],
    strategy_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Run complete pre-deployment checklist.

    Args:
        model_metrics: Model performance metrics
        walk_forward_results: Walk-forward validation results
        phase4_results: Phase 4 optimization results
        strategy_config: Final strategy configuration

    Returns:
        Dict with checklist items and their pass/fail status
    """
    # Define default thresholds
    default_thresholds = {
        "profitability_r2": 0.2,
        "diagnostic_f1": 0.6,
    }

    # Run all checks
    baselines_pass = check_model_baselines(model_metrics, default_thresholds)
    walk_forward_pass = check_walk_forward_performance(walk_forward_results)

    # Extract filter threshold from phase4_results
    filter_threshold = 0.5  # Default
    for key in phase4_results.keys():
        if key.startswith("with_filter_"):
            try:
                filter_threshold = float(key.split("_")[-1])
                break
            except ValueError:
                pass

    filter_justified, filter_message = check_filter_threshold_justified(
        phase4_results, filter_threshold
    )
    git_commit_pass = check_git_commit_exists(strategy_config)

    # Build checklist result
    checklist = {
        "model_baselines": {
            "passed": baselines_pass,
            "description": "Model performance meets minimum baselines",
            "details": (
                f"R² >= {default_thresholds['profitability_r2']}, "
                f"F1 >= {default_thresholds['diagnostic_f1']}"
            ),
        },
        "walk_forward_consistency": {
            "passed": walk_forward_pass,
            "description": (
                "Walk-forward validation shows consistent positive performance"
            ),
            "details": "All test periods have positive Sharpe ratio",
        },
        "filter_justification": {
            "passed": filter_justified,
            "description": "Predictive filter threshold is justified",
            "details": filter_message,
        },
        "git_commit": {
            "passed": git_commit_pass,
            "description": "Git commit hash recorded for reproducibility",
            "details": strategy_config.get("metadata", {}).get("git_commit", "N/A"),
        },
    }

    return checklist
