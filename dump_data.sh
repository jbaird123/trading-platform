
import pytest
from trading_platform.ai.evaluation.metrics import (
    calculate_statistical_significance,
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
