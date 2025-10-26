from __future__ import annotations

from typing import Any


def test_check_model_baselines_met() -> None:
    """Test checking if model baselines are met."""
    from trading_platform.validation.pre_deployment import check_model_baselines

    # Create mock model performance metrics
    metrics = {
        "profitability_r2": 0.3,
        "diagnostic_f1": 0.7,
    }

    # Define minimum thresholds
    thresholds = {
        "profitability_r2": 0.2,
        "diagnostic_f1": 0.6,
    }

    # Should pass - all metrics above thresholds
    assert check_model_baselines(metrics, thresholds)


def test_check_model_baselines_not_met() -> None:
    """Test when model baselines are not met."""
    from trading_platform.validation.pre_deployment import check_model_baselines

    metrics = {
        "profitability_r2": 0.15,  # Below threshold
        "diagnostic_f1": 0.7,
    }

    thresholds = {
        "profitability_r2": 0.2,
        "diagnostic_f1": 0.6,
    }

    # Should fail - profitability_r2 below threshold
    assert not check_model_baselines(metrics, thresholds)


def test_check_walk_forward_consistency() -> None:
    """Test walk-forward consistency check."""
    from trading_platform.validation.pre_deployment import (
        check_walk_forward_performance,
    )

    # Create walk-forward results with consistent positive performance
    results = {
        "2020": {"sharpe_ratio": 1.5, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": 1.6, "max_drawdown": -0.12},
        "2022": {"sharpe_ratio": 1.4, "max_drawdown": -0.18},
    }

    # Should pass - all periods have positive Sharpe ratio
    assert check_walk_forward_performance(results)


def test_check_walk_forward_inconsistent() -> None:
    """Test walk-forward with inconsistent performance."""
    from trading_platform.validation.pre_deployment import (
        check_walk_forward_performance,
    )

    # Create results with negative performance in some periods
    results = {
        "2020": {"sharpe_ratio": 1.5, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": -0.5, "max_drawdown": -0.45},
        "2022": {"sharpe_ratio": 1.4, "max_drawdown": -0.18},
    }

    # Should fail - period 2021 has negative Sharpe
    assert not check_walk_forward_performance(results)


def test_check_predictive_filter_justification() -> None:
    """Test checking if predictive filter threshold is justified."""
    from trading_platform.validation.pre_deployment import (
        check_filter_threshold_justified,
    )

    # Create Phase 4 campaign results showing improvement with filter threshold
    phase4_results = {
        "without_filter": {
            "sharpe_ratio": 1.2,
            "total_return": 0.15,
        },
        "with_filter_0.5": {
            "sharpe_ratio": 1.8,
            "total_return": 0.25,
        },
    }

    # Should be justified - significant improvement
    justified, message = check_filter_threshold_justified(phase4_results, threshold=0.5)
    assert justified
    assert "improvement" in message.lower()


def test_check_git_commit_recorded() -> None:
    """Test checking if git commit is recorded."""
    from trading_platform.validation.pre_deployment import check_git_commit_exists

    # Config with git commit
    config_with_commit = {
        "metadata": {
            "git_commit": "abc123",
        }
    }
    assert check_git_commit_exists(config_with_commit)

    # Config without git commit
    config_without_commit: dict[str, Any] = {"metadata": {}}
    assert not check_git_commit_exists(config_without_commit)


def test_full_pre_deployment_checklist() -> None:
    """Test running full pre-deployment checklist."""
    from trading_platform.validation.pre_deployment import run_pre_deployment_checklist

    # Create complete test data
    model_metrics = {
        "profitability_r2": 0.3,
        "diagnostic_f1": 0.7,
    }

    walk_forward_results = {
        "2020": {"sharpe_ratio": 1.5, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": 1.6, "max_drawdown": -0.12},
    }

    phase4_results = {
        "without_filter": {"sharpe_ratio": 1.2},
        "with_filter_0.5": {"sharpe_ratio": 1.8},
    }

    strategy_config = {
        "metadata": {"git_commit": "abc123"},
    }

    # Run full checklist
    checklist = run_pre_deployment_checklist(
        model_metrics=model_metrics,
        walk_forward_results=walk_forward_results,
        phase4_results=phase4_results,
        strategy_config=strategy_config,
    )

    # Should have all items
    assert "model_baselines" in checklist
    assert "walk_forward_consistency" in checklist
    assert "filter_justification" in checklist
    assert "git_commit" in checklist

    # All should pass
    assert checklist["model_baselines"]["passed"]
    assert checklist["walk_forward_consistency"]["passed"]
    assert checklist["filter_justification"]["passed"]
    assert checklist["git_commit"]["passed"]
