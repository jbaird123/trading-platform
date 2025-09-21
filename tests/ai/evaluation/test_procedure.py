from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from trading_platform.ai.evaluation.procedure import AIEvaluationProcedure


def test_run_cross_validation_aggregation():
    """
    Tests that the cross-validation procedure correctly aggregates metrics
    from multiple folds.
    """
    # 1. Arrange
    mock_config = {"cross_validation": {"n_splits": 2}}
    procedure = AIEvaluationProcedure(config=mock_config)

    # Mock model and data
    mock_model = MagicMock()
    X = pd.DataFrame({"feature1": [1, 2, 3, 4, 5, 6]})
    y = pd.Series([0, 1, 0, 1, 0, 1])

    # Mock TimeSeriesSplit to return predictable folds
    mock_tscv_split = [
        ([0, 1], [2, 3]),  # Fold 1
        ([0, 1, 2, 3], [4, 5]),  # Fold 2
    ]

    # Mock metrics returned per fold
    mock_fold_scores = [
        {"accuracy": 0.8, "precision": 0.7},  # Scores for Fold 1
        {"accuracy": 0.9, "precision": 0.8},  # Scores for Fold 2
    ]

    # 2. Act
    with patch(
        "trading_platform.ai.evaluation.procedure.TimeSeriesSplit"
    ) as mock_tscv, patch(
        "trading_platform.ai.evaluation.procedure.get_classification_metrics"
    ) as mock_get_metrics:
        mock_tscv.return_value.split.return_value = mock_tscv_split
        mock_get_metrics.side_effect = mock_fold_scores

        results = procedure.run_cross_validation(mock_model, X, y)

    # 3. Assert
    assert results["mean_accuracy"] == pytest.approx(0.85)
    assert results["std_accuracy"] == pytest.approx(0.07071, abs=1e-4)
    assert results["mean_precision"] == pytest.approx(0.75)
    assert results["std_precision"] == pytest.approx(0.07071, abs=1e-4)

    # Ensure the model was fitted for each fold
    assert mock_model.fit.call_count == 2
