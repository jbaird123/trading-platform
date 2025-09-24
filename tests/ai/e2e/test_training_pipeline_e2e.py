import json
import os
import shutil
from unittest.mock import patch

import mlflow
import pandas as pd
import pytest
import yaml
from trading_platform.ai.training.pipeline import AITrainingPipeline


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
        "features": [{"kind": "sma", "params": {"length": 2}, "source": "close"}],
        "labeling": {"look_ahead_bars": 1},
        "model": {"type": "random_forest", "params": {"n_estimators": 5}},
        "evaluation": {"run_cross_validation": False},
        "synthesis": {},
    }
    config_file = tmp_path / "e2e_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)
    return str(config_file)


# Mocking external dependencies for E2E test to control data and avoid
# real external calls
@pytest.fixture(autouse=True)
def mock_external_dependencies_for_e2e():
    with (
        patch(
            "trading_platform.ai.training.pipeline.DataCatalog"
        ) as mock_data_catalog_cls,
        patch(
            "trading_platform.ai.training.pipeline.lgb", new=None
        ),  # Ensure lightgbm is not imported
    ):
        # Mock DataCatalog behavior
        mock_data_catalog_instance = mock_data_catalog_cls.return_value
        mock_data_catalog_instance.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100 + i for i in range(20)],
                "high": [102 + i for i in range(20)],
                "low": [99 + i for i in range(20)],
                "close": [101 + i for i in range(20)],
                "volume": [1000 + i * 100 for i in range(20)],
            },
            index=pd.to_datetime([f"2023-01-{i+1:02d}" for i in range(20)]),
        )

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
            "end_date": "2023-01-20",
        },
        "features": [
            {
                "name": "sma_5",
                "kind": "sma",
                "params": {"length": 5},
                "source": "close",
            },
        ],
        "labeling": {
            "look_ahead_bars": 1,
        },
        "model": {
            "type": "random_forest",
            "params": {"n_estimators": 10},
        },
        "evaluation": {
            "cross_validation": {"n_splits": 2},
        },
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    # Run the pipeline
    pipeline = AITrainingPipeline(str(config_file))
    pipeline.run()

    # Basic assertions to check if MLflow logged something
    # This is a very high-level check for e2e
    assert (tmp_path / "mlruns").exists()
    # Further checks could involve parsing MLflow artifacts or checking specific metrics


def test_full_training_pipeline_e2e_minimal(minimal_training_config, temp_mlflow_uri):
    # Ensure MLflow is clean before the test
    mlflow.end_run()

    pipeline = AITrainingPipeline(minimal_training_config)
    pipeline.run()

    # Assertions for MLflow run completion and artifacts
    runs = mlflow.search_runs(experiment_names=["E2E Training Test"])
    assert len(runs) == 1
    runs_df = pd.DataFrame(runs) if not isinstance(runs, pd.DataFrame) else runs
    run_id = runs_df.iloc[0].run_id

    # Verify artifacts
    client = mlflow.tracking.MlflowClient(tracking_uri=temp_mlflow_uri)
    artifacts = client.list_artifacts(run_id)
    artifact_paths = [a.path for a in artifacts]

    assert "onnx_model" in artifact_paths  # Check for ONNX model directory
    assert "diagnostic_synthesis_results.json" in artifact_paths

    # Verify model can be loaded and makes a prediction
    loaded_model = mlflow.sklearn.load_model(f"runs:/{run_id}/model")
    # The model was trained on columns:
    # ['open', 'high', 'low', 'close', 'volume', 'sma_2']
    dummy_input = pd.DataFrame(
        [[100, 102, 99, 101, 1000, 100.5]],
        columns=["open", "high", "low", "close", "volume", "sma_2"],
    )
    prediction = loaded_model.predict(dummy_input)
    assert prediction is not None
    assert len(prediction) == 1

    # Verify ONNX model can be loaded (basic check, not full inference)
    experiment_id = runs_df.iloc[0].experiment_id
    onnx_artifact_path = os.path.join(
        temp_mlflow_uri,
        experiment_id,
        run_id,
        "artifacts",
        "onnx_model",
        "model.onnx",
    )
    assert os.path.exists(onnx_artifact_path)
    # Further ONNX validation would require onnxruntime, which might not be in test env

    # Verify diagnostic synthesis results content (basic check)
    experiment_id = runs_df.iloc[0].experiment_id
    diagnostic_results_path = os.path.join(
        temp_mlflow_uri,
        experiment_id,
        run_id,
        "artifacts",
        "diagnostic_synthesis_results.json",
    )
    assert os.path.exists(diagnostic_results_path)
    with open(diagnostic_results_path) as f:
        results = json.load(f)
        assert isinstance(results, dict)
        assert "conclusions" in results
        assert "recommendations" in results
