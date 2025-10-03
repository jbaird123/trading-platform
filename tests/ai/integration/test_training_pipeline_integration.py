from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml
from trading_platform.ai.training.pipeline import AITrainingPipeline


@pytest.fixture
def mock_training_config_path(tmp_path):
    from trading_platform.core import paths

    config_content = {
        "run_id": "integration_test_run",
        "experiment_name": "Integration Test Experiment",
        "mlflow_tracking_uri": paths.MLFLOW_TEST_URI,
        "data": {
            "symbol": "TEST",
            "timeframe": "1D",
            "start_date": "2023-01-01",
            "end_date": "2023-01-05",
        },
        "features": [{"kind": "sma", "length": 2, "source": "close"}],
        "labeling": {"look_ahead_bars": 1},
        "model": {"type": "random_forest", "params": {"n_estimators": 10}},
        "evaluation": {"run_cross_validation": False},
        "synthesis": {},
    }
    config_file = tmp_path / "integration_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)
    return str(config_file)


@patch("trading_platform.ai.training.pipeline.mlflow")
@patch("trading_platform.ai.training.pipeline.AIDataConnector")
@patch("trading_platform.ai.training.pipeline.FeatureEngineeringPipeline")
@patch("trading_platform.ai.training.pipeline.DataLabeler")
@patch("trading_platform.ai.training.pipeline.RandomForestClassifier")
@patch("trading_platform.ai.training.pipeline.AIEvaluationProcedure")
@patch("trading_platform.ai.training.pipeline.DiagnosticSynthesisEngine")
@patch("trading_platform.ai.training.pipeline.convert_sklearn")
@patch("os.remove")
def test_training_pipeline_integration_flow(
    mock_os_remove,
    mock_convert_sklearn,
    mock_synthesis_engine_cls,
    mock_eval_procedure_cls,
    mock_rf_classifier_cls,
    mock_data_labeler_cls,
    mock_feature_pipeline_cls,
    mock_data_connector_cls,
    mock_mlflow,
    mock_training_config_path,
):
    # Mock setup for data loading and preparation
    mock_data_connector_instance = mock_data_connector_cls.return_value
    mock_data_connector_instance.load_training_data.return_value = pd.DataFrame(
        {
            "open": [100] * 5,
            "high": [102] * 5,
            "low": [99] * 5,
            "close": [101] * 5,
            "volume": [1000] * 5,
        },
        index=pd.to_datetime([f"2023-01-0{i}" for i in range(1, 6)]),
    )

    mock_feature_pipeline_instance = mock_feature_pipeline_cls.return_value
    mock_feature_pipeline_instance.run.return_value = pd.DataFrame(
        {"feature1": [1, 2, 3, 4, 5], "feature2": [5, 4, 3, 2, 1]},
        index=pd.to_datetime([f"2023-01-0{i}" for i in range(1, 6)]),
    )

    mock_data_labeler_instance = mock_data_labeler_cls.return_value
    mock_data_labeler_instance.generate_future_price_direction.return_value = pd.Series(
        [0, 1, 0, 1, 0], index=pd.to_datetime([f"2023-01-0{i}" for i in range(1, 6)])
    )

    # Mock setup for model training
    mock_trained_model = mock_rf_classifier_cls.return_value

    # Mock setup for evaluation
    mock_eval_procedure_instance = mock_eval_procedure_cls.return_value
    mock_eval_procedure_instance.run.return_value = {"accuracy": 0.95}

    # Mock setup for synthesis engine
    mock_synthesis_engine_instance = mock_synthesis_engine_cls.return_value
    mock_synthesis_engine_instance.generate_report_json.return_value = (
        '{"report": "mock_report"}'
    )

    # Mock ONNX conversion
    mock_onnx_model = MagicMock()
    mock_onnx_model.SerializeToString.return_value = b"dummy_onnx_model_bytes"
    mock_convert_sklearn.return_value = mock_onnx_model

    # Instantiate and run the pipeline
    pipeline = AITrainingPipeline(mock_training_config_path)
    pipeline.run()

    # Assertions for MLflow run context
    mock_mlflow.start_run.assert_called_once_with(run_name="integration_test_run")
    mock_mlflow.log_params.assert_called_once()

    # Assertions for data loading and preparation
    mock_data_connector_cls.assert_called_once()
    mock_data_connector_instance.load_training_data.assert_called_once()
    mock_feature_pipeline_cls.assert_called_once()
    mock_feature_pipeline_instance.run.assert_called_once()
    mock_data_labeler_cls.assert_called_once()
    mock_data_labeler_instance.generate_future_price_direction.assert_called_once()

    # Assertions for model training
    mock_rf_classifier_cls.assert_called_once_with(n_estimators=10)
    mock_trained_model.fit.assert_called_once()

    # Assertions for evaluation and artifact logging
    mock_eval_procedure_cls.assert_called_once()
    mock_eval_procedure_instance.run.assert_called_once()
    mock_mlflow.log_metrics.assert_called_once_with({"accuracy": 0.95})
    mock_mlflow.sklearn.log_model.assert_called_once_with(mock_trained_model, "model")
    mock_convert_sklearn.assert_called_once()
    mock_mlflow.log_artifact.assert_called_once_with("model.onnx", "onnx_model")
    mock_os_remove.assert_called_once_with("model.onnx")

    # Assertions for diagnostic synthesis engine
    mock_synthesis_engine_cls.assert_called_once()
    mock_synthesis_engine_instance.run.assert_called_once()
    mock_synthesis_engine_instance.generate_report_json.assert_called_once()
    mock_mlflow.log_dict.assert_called_once_with(
        {"report": "mock_report"}, "diagnostic_synthesis_results.json"
    )
