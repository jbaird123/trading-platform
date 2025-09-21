from unittest.mock import patch

import pandas as pd
import pytest
import yaml
from trading_platform.ai.training.pipeline import AITrainingPipeline


@pytest.fixture
def dummy_config_file(tmp_path):
    """Creates a dummy YAML config file for testing."""
    config = {
        "run_id": "test_run_123",
        "experiment_name": "Test Experiment",
        "data": {},
        "features": [],
        "labeling": {},
        "model": {"type": "random_forest"},
        "evaluation": {"run_cross_validation": True},
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return str(config_path)


@patch("trading_platform.ai.training.pipeline.mlflow")
@patch("trading_platform.ai.training.pipeline.AIEvaluationProcedure")
@patch("trading_platform.ai.training.pipeline.DataLabeler")
@patch("trading_platform.ai.training.pipeline.FeatureEngineeringPipeline")
@patch("trading_platform.ai.training.pipeline.AIDataConnector")
def test_pipeline_run_integrates_mlflow(
    mock_connector,
    mock_feat_pipe,
    mock_labeler,
    mock_eval_proc,
    mock_mlflow,
    dummy_config_file,
):
    """
    Tests that the AITrainingPipeline.run method correctly integrates with MLflow.
    """
    # Arrange
    # Mock components to return real, empty pandas objects to avoid recursion errors
    mock_connector.return_value.load_training_data.return_value = pd.DataFrame(
        {"close": [1, 2, 3]}
    )
    mock_feat_pipe.return_value.run.return_value = pd.DataFrame(
        {"close": [1, 2, 3], "sma_10": [1, 2, 3]}
    )
    mock_labeler.return_value.generate_future_price_direction.return_value = pd.Series(
        [0, 1, 0]
    )
    mock_eval_proc.return_value.run.return_value = {
        "cross_validation.mean_accuracy": 0.95
    }

    # Instantiate the pipeline with the dummy config
    pipeline = AITrainingPipeline(config_path=dummy_config_file)

    # Act
    pipeline.run()

    # Assert
    mock_mlflow.start_run.assert_called_once()
    mock_mlflow.log_params.assert_called_once()
    mock_mlflow.log_metrics.assert_called_once()
    mock_mlflow.sklearn.log_model.assert_called_once()

    # Verify that the correct metric was logged
    call_args, _ = mock_mlflow.log_metrics.call_args
    assert call_args[0]["cross_validation.mean_accuracy"] == 0.95
