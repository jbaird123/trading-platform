import warnings
from unittest import mock
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit
from sklearn.exceptions import UndefinedMetricWarning
from trading_platform.ai.evaluation.procedure import AIEvaluationProcedure


# Mock a simple model for testing purposes
class MockModel:
    def fit(self, X, y):
        pass

    def predict(self, X):
        return pd.Series([0] * len(X))

    def predict_proba(self, X):
        return np.array([[0.5, 0.5]] * len(X))


@pytest.fixture
def sample_data():
    X = pd.DataFrame({"feature1": range(10), "feature2": range(10, 20)})
    y = pd.Series([i % 2 for i in range(10)])
    return X, y


@pytest.fixture
def mock_model():
    return MockModel()


@pytest.fixture
def default_config():
    config: dict[str, object] = {"cross_validation": {"n_splits": 3}}
    return config


class TestAIEvaluationProcedure:
    def test_init(self, default_config):
        procedure = AIEvaluationProcedure(default_config)
        assert procedure.config == default_config

    @mock.patch("trading_platform.ai.evaluation.procedure.get_classification_metrics")
    @mock.patch("trading_platform.ai.evaluation.procedure.TimeSeriesSplit")
    def test_run_cross_validation_basic(
        self,
        mock_tscv,
        mock_get_classification_metrics,
        mock_model,
        sample_data,
        default_config,
    ):
        X, y = sample_data

        # Configure TimeSeriesSplit mock
        mock_tscv_instance = mock.Mock(spec=TimeSeriesSplit)
        mock_tscv.return_value = mock_tscv_instance
        mock_tscv_instance.split.return_value = [
            ([0, 1], [2, 3]),
            ([0, 1, 2, 3], [4, 5]),
            ([0, 1, 2, 3, 4, 5], [6, 7]),
        ]

        # Configure get_classification_metrics mock
        mock_get_classification_metrics.side_effect = [
            {"accuracy": 0.8, "precision": 0.7},
            {"accuracy": 0.9, "precision": 0.8},
            {"accuracy": 0.7, "precision": 0.6},
        ]

        procedure = AIEvaluationProcedure(default_config)
        results = procedure.run_cross_validation(mock_model, X, y)

        assert "mean_accuracy" in results
        assert "mean_precision" in results
        assert "std_accuracy" in results
        assert "std_precision" in results
        assert pytest.approx(results["mean_accuracy"]) == (0.8 + 0.9 + 0.7) / 3


# --- Consolidated from tests/ai/test_evaluation_coverage_gaps.py ---

    def test_run_cross_validation_handles_1d_probability(self):
        """Cross-validation should tolerate 1D probability outputs."""
        X = pd.DataFrame(
            {"feature1": [1, 2, 3, 4, 5, 6], "feature2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
        )
        y = pd.Series([0, 1, 0, 1, 0, 1])

        mock_model = Mock()
        mock_model.fit.return_value = mock_model
        mock_model.predict.return_value = np.array([0, 1, 0])
        mock_model.predict_proba.return_value = np.array([0.2, 0.8, 0.3])

        evaluator = AIEvaluationProcedure({"cross_validation": {"n_splits": 2}})

        with mock.patch(
            "trading_platform.ai.evaluation.procedure.TimeSeriesSplit"
        ) as mock_tscv:
            mock_tscv.return_value.split.return_value = [
                (np.array([0, 1, 2]), np.array([3, 4, 5]))
            ]

            results = evaluator.run_cross_validation(mock_model, X, y)

        assert isinstance(results, dict)
        assert results

    def test_run_cross_validation_handles_2d_probability(self):
        """Cross-validation should accept 2D probability arrays."""
        X = pd.DataFrame(
            {"feature1": [1, 2, 3, 4, 5, 6], "feature2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
        )
        y = pd.Series([0, 1, 0, 1, 0, 1])

        mock_model = Mock()
        mock_model.fit.return_value = mock_model
        mock_model.predict.return_value = np.array([0, 1, 0])
        mock_model.predict_proba.return_value = np.array(
            [[0.8, 0.2], [0.3, 0.7], [0.6, 0.4]]
        )

        evaluator = AIEvaluationProcedure({"cross_validation": {"n_splits": 2}})

        with mock.patch(
            "trading_platform.ai.evaluation.procedure.TimeSeriesSplit"
        ) as mock_tscv:
            mock_tscv.return_value.split.return_value = [
                (np.array([0, 1, 2]), np.array([3, 4, 5]))
            ]

            results = evaluator.run_cross_validation(mock_model, X, y)

        assert isinstance(results, dict)
        assert results

    @mock.patch("trading_platform.ai.evaluation.procedure.get_classification_metrics")
    @mock.patch("trading_platform.ai.evaluation.procedure.TimeSeriesSplit")
    def test_run_cross_validation_n_splits_from_config(
        self,
        mock_tscv,
        mock_get_classification_metrics,
        mock_model,
        sample_data,
    ):
        X, y = sample_data
        config: dict[str, object] = {"cross_validation": {"n_splits": 2}}

        mock_tscv_instance = mock.Mock(spec=TimeSeriesSplit)
        mock_tscv.return_value = mock_tscv_instance
        mock_tscv_instance.split.return_value = [
            ([0, 1, 2, 3], [4, 5]),
            ([0, 1, 2, 3, 4, 5], [6, 7]),
        ]

        mock_get_classification_metrics.side_effect = [
            {"accuracy": 0.8},
            {"accuracy": 0.9},
        ]

        procedure = AIEvaluationProcedure(config)
        procedure.run_cross_validation(mock_model, X, y)

        mock_tscv.assert_called_once_with(n_splits=2)
        assert mock_get_classification_metrics.call_count == 2
    @mock.patch("trading_platform.ai.evaluation.procedure.get_classification_metrics")
    @mock.patch("trading_platform.ai.evaluation.procedure.TimeSeriesSplit")
    def test_run_cross_validation_no_cv_config(
        self,
        mock_tscv,
        mock_get_classification_metrics,
        mock_model,
        sample_data,
    ):
        X, y = sample_data
        config: dict[str, object] = {}  # No cross_validation key

        mock_tscv_instance = mock.Mock(spec=TimeSeriesSplit)
        mock_tscv.return_value = mock_tscv_instance
        # Ensure all folds have non-empty test sets
        mock_tscv_instance.split.return_value = [
            ([0, 1], [2]),
            ([0, 1, 2], [3]),
            ([0, 1, 2, 3], [4]),
            ([0, 1, 2, 3, 4], [5]),
            ([0, 1, 2, 3, 4, 5], [6]),
        ]

        mock_get_classification_metrics.side_effect = [
            {"accuracy": 0.8},
            {"accuracy": 0.9},
            {"accuracy": 0.7},
            {"accuracy": 0.85},
            {"accuracy": 0.75},
        ]

        procedure = AIEvaluationProcedure(config)
        procedure.run_cross_validation(mock_model, X, y)

        mock_tscv.assert_called_once_with(n_splits=5)  # Default n_splits

    def test_run_stress_testing_placeholder(self, mock_model, sample_data, capsys):
        X, _ = sample_data
        config: dict[str, bool] = {"run_stress_testing": True}
        procedure = AIEvaluationProcedure(config)
        results = procedure.run_stress_testing(mock_model, X)

        assert results == {"performance_in_high_vol": "degraded"}
        captured = capsys.readouterr()
        assert "Performing stress testing (placeholder)" in captured.out

    def test_run_bias_detection_placeholder(self, mock_model, sample_data, capsys):
        X, _ = sample_data
        config: dict[str, bool] = {"run_bias_detection": True}
        procedure = AIEvaluationProcedure(config)
        results = procedure.run_bias_detection(mock_model, X)

        assert results == {"bias_found": "none"}
        captured = capsys.readouterr()
        assert "Performing bias detection (placeholder)" in captured.out

    def test_run_full_pipeline_execution(self, mock_model, sample_data, capsys):
        X, y = sample_data
        config = {
            "run_cross_validation": True,
            "run_stress_testing": True,
            "run_bias_detection": True,
        }
        procedure = AIEvaluationProcedure(config)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UndefinedMetricWarning)
            results = procedure.run(mock_model, X, y)

        assert "cross_validation" in results
        assert "stress_testing" in results
        assert "bias_detection" in results

        output = capsys.readouterr().out
        assert "--- Starting AI Evaluation Procedure ---" in output
        assert "Cross-validation complete." in output
        assert "Stress testing complete." in output
        assert "Bias detection complete." in output
        assert "--- AI Evaluation Procedure finished successfully. ---" in output

    @mock.patch.object(AIEvaluationProcedure, "run_bias_detection")
    @mock.patch.object(AIEvaluationProcedure, "run_stress_testing")
    @mock.patch.object(AIEvaluationProcedure, "run_cross_validation")
    def test_run_all_enabled(
        self,
        mock_run_cv,
        mock_run_stress,
        mock_run_bias,
        mock_model,
        sample_data,
    ):
        X, y = sample_data
        config: dict[str, bool] = {
            "run_cross_validation": True,
            "run_stress_testing": True,
            "run_bias_detection": True,
        }
        mock_run_cv.return_value = {"cv_results": "mocked"}
        mock_run_stress.return_value = {"stress_results": "mocked"}
        mock_run_bias.return_value = {"bias_results": "mocked"}

        procedure = AIEvaluationProcedure(config)
        results = procedure.run(mock_model, X, y)

        mock_run_cv.assert_called_once_with(mock_model, X, y)
        mock_run_stress.assert_called_once_with(mock_model, X)
        mock_run_bias.assert_called_once_with(mock_model, X)
        assert results == {
            "cross_validation": {"cv_results": "mocked"},
            "stress_testing": {"stress_results": "mocked"},
            "bias_detection": {"bias_results": "mocked"},
        }

    @mock.patch.object(AIEvaluationProcedure, "run_bias_detection")
    @mock.patch.object(AIEvaluationProcedure, "run_stress_testing")
    @mock.patch.object(AIEvaluationProcedure, "run_cross_validation")
    def test_run_only_cv_enabled(
        self,
        mock_run_cv,
        mock_run_stress,
        mock_run_bias,
        mock_model,
        sample_data,
    ):
        X, y = sample_data
        config: dict[str, bool] = {"run_cross_validation": True}
        mock_run_cv.return_value = {"cv_results": "mocked"}

        procedure = AIEvaluationProcedure(config)
        results = procedure.run(mock_model, X, y)

        mock_run_cv.assert_called_once_with(mock_model, X, y)
        mock_run_stress.assert_not_called()
        mock_run_bias.assert_not_called()
        assert results == {"cross_validation": {"cv_results": "mocked"}}

    @mock.patch.object(AIEvaluationProcedure, "run_bias_detection")
    @mock.patch.object(AIEvaluationProcedure, "run_stress_testing")
    @mock.patch.object(AIEvaluationProcedure, "run_cross_validation")
    def test_run_none_enabled(
        self,
        mock_run_cv,
        mock_run_stress,
        mock_run_bias,
        mock_model,
        sample_data,
    ):
        X, y = sample_data
        config: dict[str, bool] = {}

        procedure = AIEvaluationProcedure(config)
        results = procedure.run(mock_model, X, y)

        mock_run_cv.assert_not_called()
        mock_run_stress.assert_not_called()
        mock_run_bias.assert_not_called()
        assert results == {}
