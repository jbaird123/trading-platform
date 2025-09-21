import pytest
import pandas as pd
import yaml
import os
import shutil
import mlflow
import json
from unittest.mock import patch

from src.trading_platform.ai.training.pipeline import AITrainingPipeline
from src.trading_platform.ai.data_connectors import DataCatalog

# Fixture for a temporary MLflow tracking URI
@pytest.fixture(scope="module")
def temp_mlflow_uri(tmp_path_factory):
    uri = tmp_path_factory.mktemp("mlruns_e2e")
    yield str(uri)
    # Clean up after tests
    if os.path.exists(uri):
        shutil.rmtree(uri)

# Fixture for a minimal training config
@pytest.fixture
def minimal_training_config(tmp_path, temp_mlflow_uri):
    config_content = {
        "run_id": "e2e_test_run",
        "experiment_name": "E2E Training Test",
        "mlflow_tracking_uri": temp_mlflow_uri,
        "data": {
            "symbol": "E2E_TEST",
            "timeframe": "1D",
            "start_date": "2023-01-01",
            "end_date": "2023-01-05",
        },
        "features": [{"kind": "sma", "length": 2, "source": "close"}],
        "labeling": {"look_ahead_bars": 1},
        "model": {"type": "random_forest", "params": {"n_estimators": 5}},
        "evaluation": {"run_cross_validation": False},
        "synthesis": {},
    }
    config_file = tmp_path / "e2e_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)
    return str(config_file)

# Mocking external dependencies for E2E test to control data and avoid real external calls
@pytest.fixture(autouse=True)
def mock_external_dependencies_for_e2e():
    with (
        patch("src.trading_platform.ai.data_connectors.DataCatalog") as mock_data_catalog_cls,
        patch("src.trading_platform.ai.training.pipeline.lgb", new=None), # Ensure lightgbm is not imported
    ):
        # Mock DataCatalog behavior
        mock_data_catalog_instance = mock_data_catalog_cls.return_value
        mock_data_catalog_instance.get_historical_data.return_value = pd.DataFrame({
            "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "high": [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            "low": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
            "close": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
        }, index=pd.to_datetime([f"2023-01-{i+1:02d}" for i in range(10)]))

        yield


def test_full_training_pipeline_e2e(tmp_path):
    # Create a dummy config file
    config_content = {
        "run_id": "e2e_test_run",
        "experiment_name": "E2E Test Experiment",
        "mlflow_tracking_uri": f"file://{tmp_path}/mlruns",
        "data": {
            "symbol": "TEST",
            "timeframe": "1D",
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
        },
        "features": [
            {"name": "sma_5", "type": "SMA", "params": {"length": 5}, "source": "close"},
        ],
        "labeling": {
            "look_ahead_bars": 1,
            "price_change_threshold": 0.001,
        },
        "model": {
            "type": "lightgbm",
            "params": {"n_estimators": 10},
        },
        "evaluation": {
            "cross_validation": {"n_splits": 2},
        },
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_content, f)

    # Run the pipeline
    pipeline = AITrainingPipeline(str(config_path))
    pipeline.run()

    # Basic assertions to check if MLflow logged something
    # This is a very high-level check for e2e
    assert (tmp_path / "mlruns").exists()
    # Further checks could involve parsing MLflow artifacts or checking specific metrics

    yield


def test_full_training_pipeline_e2e(minimal_training_config, temp_mlflow_uri):
    # Ensure MLflow is clean before the test
    mlflow.end_run()
    
    pipeline = AITrainingPipeline(minimal_training_config)
    pipeline.run()

    # Assertions for MLflow run completion and artifacts
    runs = mlflow.search_runs(experiment_names=["E2E Training Test"])
    assert len(runs) == 1
    run_id = runs.iloc[0].run_id

    # Verify artifacts
    client = mlflow.tracking.MlflowClient(tracking_uri=temp_mlflow_uri)
    artifacts = client.list_artifacts(run_id)
    artifact_paths = [a.path for a in artifacts]

    assert "model" in artifact_paths # MLflow model directory
    assert "onnx_model" in artifact_paths # ONNX model directory
    assert "diagnostic_synthesis_results.json" in artifact_paths

    # Verify model can be loaded and makes a prediction
    loaded_model = mlflow.sklearn.load_model(f"runs:/{run_id}/model")
    dummy_input = pd.DataFrame([[1.0, 2.0]], columns=["feature1", "feature2"]) # Dummy input for prediction
    prediction = loaded_model.predict(dummy_input)
    assert prediction is not None
    assert len(prediction) == 1

    # Verify ONNX model can be loaded (basic check, not full inference)
    onnx_artifact_path = os.path.join(temp_mlflow_uri, run_id, "artifacts", "onnx_model", "model.onnx")
    assert os.path.exists(onnx_artifact_path)
    # Further ONNX validation would require onnxruntime, which might not be in test env

    # Verify diagnostic synthesis results content (basic check)
    diagnostic_results_path = os.path.join(temp_mlflow_uri, run_id, "artifacts", "diagnostic_synthesis_results.json")
    assert os.path.exists(diagnostic_results_path)
    with open(diagnostic_results_path, "r") as f:
        results = json.load(f)
        assert "report" in results # Check for expected key from mock
