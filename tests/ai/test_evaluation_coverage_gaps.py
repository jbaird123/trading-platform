"""
Test coverage gaps in AI Evaluation modules.

Targets specific missing lines in ai/evaluation/ modules to improve coverage.
"""

from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from trading_platform.ai.evaluation.metrics import (
    calculate_sortino_ratio,
    get_classification_metrics,
)
from trading_platform.ai.evaluation.procedure import AIEvaluationProcedure


def test_sortino_ratio_zero_downside_std():
    """Downside std at zero should yield sortino ratio of 0. (line 54)."""
    # Create PnL series with identical negative returns (std = 0)
    pnl_series = pd.Series([-1.0, -1.0, -1.0, -1.0, -1.0])

    # When all downside returns are identical, std should be 0
    result = calculate_sortino_ratio(pnl_series)

    # Should return 0.0 when downside_std == 0
    assert result == 0.0


def test_sortino_ratio_no_downside_returns():
    """Test calculate_sortino_ratio with only positive returns."""
    # Create PnL series with only positive returns
    pnl_series = pd.Series([1.0, 2.0, 1.5, 3.0, 2.5])

    result = calculate_sortino_ratio(pnl_series)

    # Should return 0.0 when no downside returns exist
    assert result == 0.0


def test_sortino_ratio_normal_case():
    """Test calculate_sortino_ratio with mixed returns."""
    # Create PnL series with mixed positive and negative returns
    pnl_series = pd.Series([1.0, -0.5, 2.0, -1.0, 1.5, -0.3])

    result = calculate_sortino_ratio(pnl_series, periods_per_year=252)

    # Should calculate normally when downside returns exist with std > 0
    assert isinstance(result, float)
    assert not np.isnan(result)


def test_evaluation_procedure_cross_validation_1d_prob():
    """Cross-validation should handle 1D probability arrays (line 52)."""
    # Create sample data
    X = pd.DataFrame(
        {"feature1": [1, 2, 3, 4, 5, 6], "feature2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
    )
    y = pd.Series([0, 1, 0, 1, 0, 1])

    # Mock model that returns 1D probability array (line 52 case)
    mock_model = Mock()
    mock_model.fit.return_value = mock_model
    mock_model.predict.return_value = np.array([0, 1, 0])
    mock_model.predict_proba.return_value = np.array([0.2, 0.8, 0.3])  # 1D array

    config = {"cross_validation": {"n_splits": 2}}
    evaluator = AIEvaluationProcedure(config)

    with patch("trading_platform.ai.evaluation.procedure.TimeSeriesSplit") as mock_tscv:
        # Mock cross-validation splits
        mock_tscv.return_value.split.return_value = [
            (np.array([0, 1, 2]), np.array([3, 4, 5]))
        ]

        result = evaluator.run_cross_validation(mock_model, X, y)

        # Should handle 1D probability array correctly
        assert isinstance(result, dict)
        assert len(result) > 0


def test_evaluation_procedure_cross_validation_2d_prob():
    """Test AIEvaluationProcedure cross-validation with 2D probability array."""
    # Create sample data
    X = pd.DataFrame(
        {"feature1": [1, 2, 3, 4, 5, 6], "feature2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
    )
    y = pd.Series([0, 1, 0, 1, 0, 1])

    # Mock model that returns 2D probability array
    mock_model = Mock()
    mock_model.fit.return_value = mock_model
    mock_model.predict.return_value = np.array([0, 1, 0])
    mock_model.predict_proba.return_value = np.array(
        [[0.8, 0.2], [0.3, 0.7], [0.6, 0.4]]
    )

    config = {"cross_validation": {"n_splits": 2}}
    evaluator = AIEvaluationProcedure(config)

    with patch("trading_platform.ai.evaluation.procedure.TimeSeriesSplit") as mock_tscv:
        # Mock cross-validation splits
        mock_tscv.return_value.split.return_value = [
            (np.array([0, 1, 2]), np.array([3, 4, 5]))
        ]

        result = evaluator.run_cross_validation(mock_model, X, y)

        # Should handle 2D probability array correctly
        assert isinstance(result, dict)
        assert len(result) > 0


def test_get_classification_metrics_comprehensive():
    """Test get_classification_metrics with various scenarios."""
    # Test with perfect predictions
    y_true = pd.Series([0, 1, 0, 1, 0])
    y_pred = pd.Series([0, 1, 0, 1, 0])
    y_prob = pd.Series([0.1, 0.9, 0.2, 0.8, 0.1])

    result = get_classification_metrics(y_true, y_pred, y_prob)

    # Should return dictionary with standard classification metrics
    expected_keys = ["accuracy", "precision", "recall", "f1_score", "roc_auc"]
    for key in expected_keys:
        assert key in result
        assert isinstance(result[key], float)

    # Perfect predictions should have high accuracy
    assert result["accuracy"] == 1.0
