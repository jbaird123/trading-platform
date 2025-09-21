import pytest
import pandas as pd
import yaml
import os
import shutil
import mlflow

from src.trading_platform.ai.training.pipeline import AITrainingPipeline

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
        # Mock DataCatalog to return dummy data
        mock_data_catalog_instance = mock_data_catalog_cls.return_value
        mock_data_catalog_instance.get_data.return_value = pd.DataFrame({
            "timestamp": pd.to_datetime([f"2023-01-0{i}" for i in range(1, 6)]),
            "open": [100, 101, 102, 103, 104],
            "high": [102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103],
            "close": [101, 102, 103, 104, 105],
            "volume": [1000, 1100, 1200, 1300, 1400],
        }).set_index("timestamp")

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
