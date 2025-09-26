import numpy as np
import pandas as pd

from trading_platform.ai.evaluation.metrics import (
    calculate_sortino_ratio,
    calculate_statistical_significance,
    get_classification_metrics,
)


def test_calculate_statistical_significance_significant_difference():
    """
    Tests that the t-test correctly identifies a statistically
    significant difference between two sets of scores.
    """
    # Arrange: Two score distributions with a clear difference in means
    scores_a = [0.8, 0.81, 0.82, 0.79, 0.83, 0.81, 0.82]
    scores_b = [0.6, 0.61, 0.62, 0.59, 0.63, 0.61, 0.62]

    # Act
    results = calculate_statistical_significance(scores_a, scores_b)

    # Assert
    assert "t_statistic" in results
    assert "p_value" in results
    assert results["p_value"] < 0.05  # Expecting a significant p-value
    assert results["t_statistic"] > 0  # Expecting a positive t-statistic


def test_calculate_statistical_significance_no_difference():
    """
    Tests that the t-test correctly identifies no statistically
    significant difference between two similar sets of scores.
    """
    # Arrange: Two score distributions with similar means
    scores_a = [0.8, 0.81, 0.82, 0.79, 0.83, 0.81, 0.82]
    scores_c = [0.81, 0.82, 0.83, 0.8, 0.84, 0.82, 0.83]

    # Act
    results = calculate_statistical_significance(scores_a, scores_c)

    # Assert
    assert "t_statistic" in results
    assert "p_value" in results
    assert results["p_value"] > 0.05  # Expecting a non-significant p-value


# --- Consolidated from tests/ai/test_evaluation_coverage_gaps.py ---


def test_sortino_ratio_zero_downside_std() -> None:
    """Downside standard deviation of zero should yield a sortino ratio of 0."""
    pnl_series = pd.Series([-1.0, -1.0, -1.0, -1.0, -1.0])
    assert calculate_sortino_ratio(pnl_series) == 0.0


def test_sortino_ratio_no_downside_returns() -> None:
    """Positive-only returns produce a sortino ratio of 0."""
    pnl_series = pd.Series([1.0, 2.0, 1.5, 3.0, 2.5])
    assert calculate_sortino_ratio(pnl_series) == 0.0


def test_sortino_ratio_normal_case() -> None:
    """Mixed returns should compute a finite sortino ratio."""
    pnl_series = pd.Series([1.0, -0.5, 2.0, -1.0, 1.5, -0.3])
    result = calculate_sortino_ratio(pnl_series, periods_per_year=252)
    assert isinstance(result, float)
    assert not np.isnan(result)


def test_get_classification_metrics_comprehensive() -> None:
    """Classification metric helper returns comprehensive results."""
    y_true = pd.Series([0, 1, 0, 1, 0])
    y_pred = pd.Series([0, 1, 0, 1, 0])
    y_prob = pd.Series([0.1, 0.9, 0.2, 0.8, 0.1])

    result = get_classification_metrics(y_true, y_pred, y_prob)
    expected_keys = ["accuracy", "precision", "recall", "f1_score", "roc_auc"]
    for key in expected_keys:
        assert key in result
        assert isinstance(result[key], float)

    assert result["accuracy"] == 1.0
