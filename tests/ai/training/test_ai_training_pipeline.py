from pathlib import Path
from pathlib import Path
from unittest import mock
import pandas as pd
import pytest
import yaml
import logging
from typing import Tuple
import numpy as np

from src.trading_platform.ai.training.pipeline import AITrainingPipeline, _flatten_dict
from src.trading_platform.ai.data_connectors import AIDataConnector
from src.trading_platform.data.loader import DataCatalog
from src.trading_platform.ai.data_labeling import DataLabeler
from src.trading_platform.ai.feature_engineering.pipeline import FeatureEngineeringPipeline
from src.trading_platform.ai.evaluation.procedure import AIEvaluationProcedure
from src.trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine

# Fixtures for configuration files
@pytest.fixture
def minimal_training_config(tmp_path):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "E2E Training Test",
        "mlflow_tracking_uri": str(tmp_path / "mlruns_e2e"),
        "data": {
            "symbol": "E2E_TEST",
            "timeframe": "1D",
            "start_date": "2023-01-01",
            "end_date": "2023-01-05",
        },
        "features": [
            {"name": "test_feature", "type": "SMA", "params": {"length": 2}, "source": "close"}
        ],
        "labeling": {"look_ahead_bars": 1, "price_change_threshold": 0.001},
        "model": {"type": "random_forest"},
        "evaluation": {"cross_validation": {"n_splits": 2}},
    }
    config_path = tmp_path / "e2e_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_content, f)
    return str(config_path)


@pytest.fixture
def temp_mlflow_uri(tmp_path):
    return str(tmp_path / "mlruns_e2e")


class MockModel:
    def fit(self, X, y):
        pass

    def predict(self, X):
        return pd.Series([0] * len(X))

    def predict_proba(self, X):
        return np.array([[0.5, 0.5]] * len(X))


# Test cases for AITrainingPipeline

def test_aitp_init(minimal_training_config):
    pipeline = AITrainingPipeline(minimal_training_config)
    assert pipeline.config["run_id"] == "test_run"
    assert pipeline.config["experiment_name"] == "E2E Training Test"


def test_aitp_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        AITrainingPipeline("non_existent_config.yaml")


def test_aitp_load_config_invalid_yaml(tmp_path):
    invalid_config_file = tmp_path / "invalid.yaml"
    invalid_config_file.write_text("key: - value")  # Invalid YAML syntax
    with pytest.raises(yaml.YAMLError):
        AITrainingPipeline(str(invalid_config_file))


@mock.patch("src.trading_platform.ai.data_connectors.AIDataConnector")
@mock.patch("src.trading_platform.ai.data_labeling.DataLabeler")
@mock.patch(
    "src.trading_platform.ai.feature_engineering.pipeline.FeatureEngineeringPipeline"
)
@mock.patch("src.trading_platform.ai.training.pipeline.DataCatalog")
def test_aitp_load_and_prepare_data(
    mock_feature_pipeline_cls,
    mock_data_labeler_cls,
    mock_data_connector_cls,
    mock_data_catalog_cls,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)

    # Mock DataCatalog's get_historical_data
    mock_data_catalog_instance = mock_data_catalog_cls.return_value
    mock_data_catalog_instance.get_historical_data.return_value = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [1, 2, 3, 4, 5],
            "low": [1, 2, 3, 4, 5],
            "close": [1, 2, 3, 4, 5],
            "volume": [1, 2, 3, 4, 5],
        },
        index=pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
            ]
        ),
    )

    # Mock data connector
    mock_data_connector_instance = mock_data_connector_cls.return_value
    mock_data_connector_instance.load_training_data.return_value = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}
    )

    # Mock feature engineering pipeline
    mock_feature_pipeline_instance = mock_feature_pipeline_cls.return_value
    mock_feature_pipeline_instance.run.return_value = pd.DataFrame(
        {"feature1": [10], "feature2": [20]}, index=pd.to_datetime(["2023-01-01"])
    )

    # Mock data labeler
    mock_data_labeler_instance = mock_data_labeler_cls.return_value
    mock_data_labeler_instance.generate_future_price_direction.return_value = pd.Series(
        [1], index=pd.to_datetime(["2023-01-01"])
    )

    X, y = pipeline._load_and_prepare_data()

    mock_data_catalog_cls.assert_called_once()
    mock_data_catalog_instance.get_historical_data.assert_called_once_with(
        symbol="E2E_TEST", timeframe="1D", start_date="2023-01-01", end_date="2023-01-05"
    )
    mock_data_connector_cls.assert_called_once_with(mock_data_catalog_instance)
    mock_data_connector_instance.load_training_data.assert_called_once_with(
        symbol="E2E_TEST", timeframe="1D", start_date="2023-01-01", end_date="2023-01-05"
    )
    mock_feature_pipeline_cls.assert_called_once()
    mock_feature_pipeline_instance.run.assert_called_once_with(
        mock_data_connector_instance.load_training_data.return_value,
        pipeline.config["features"],
    )
    mock_data_labeler_cls.assert_called_once()
    mock_data_labeler_instance.generate_future_price_direction.assert_called_once_with(
        mock_feature_pipeline_instance.run.return_value
    )

    assert isinstance(X, pd.DataFrame)
    assert isinstance(y, pd.Series)
    assert X.shape == (1, 2)
    assert y.shape == (1,)
    assert X.index.equals(y.index)


@mock.patch("src.trading_platform.ai.data_connectors.AIDataConnector")
@mock.patch("src.trading_platform.ai.data_labeling.DataLabeler")
@mock.patch(
    "src.trading_platform.ai.feature_engineering.pipeline.FeatureEngineeringPipeline"
)
@mock.patch("src.trading_platform.ai.training.pipeline.DataCatalog")
def test_aitp_load_and_prepare_data_with_nans(
    mock_feature_pipeline_cls,
    mock_data_labeler_cls,
    mock_data_connector_cls,
    mock_data_catalog_cls,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)

    # Mock DataCatalog's get_historical_data
    mock_data_catalog_instance = mock_data_catalog_cls.return_value
    mock_data_catalog_instance.get_historical_data.return_value = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [1, 2, 3, 4, 5],
            "low": [1, 2, 3, 4, 5],
            "close": [1, 2, 3, 4, 5],
            "volume": [1, 2, 3, 4, 5],
        },
        index=pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
            ]
        ),
    )

    mock_data_connector_instance = mock_data_connector_cls.return_value
    mock_data_connector_instance.load_training_data.return_value = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}
    )

    mock_feature_pipeline_instance = mock_feature_pipeline_cls.return_value
    # Simulate NaNs in featured_df
    featured_df_with_nan = pd.DataFrame(
        {"feature1": [10, None], "feature2": [20, 30]},
        index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
    )
    mock_feature_pipeline_instance.run.return_value = featured_df_with_nan

    mock_data_labeler_instance = mock_data_labeler_cls.return_value
    labels = pd.Series([1, 0], index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
    mock_data_labeler_instance.generate_future_price_direction.return_value = labels

    X, y = pipeline._load_and_prepare_data()

    assert X.shape == (1, 2)  # NaN row should be dropped
    assert y.shape == (1,)
    assert X.index.equals(y.index)
    assert not X.isnull().any().any()
    assert not y.isnull().any()


@mock.patch("src.trading_platform.ai.training.pipeline.lgb")
@mock.patch("sklearn.ensemble.RandomForestClassifier")
@mock.patch("sklearn.model_selection.GridSearchCV")
def test_aitp_train_model_lightgbm_no_tuning(
    mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "lightgbm", "params": {"n_estimators": 50}},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "lgbm_no_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    mock_lgb_classifier_instance = mock_lgb.LGBMClassifier.return_value
    trained_model = pipeline._train_model(X, y)

    mock_lgb.LGBMClassifier.assert_called_once_with(n_estimators=50)
    mock_lgb_classifier_instance.fit.assert_called_once_with(X, y)
    mock_grid_search_cv.assert_not_called()
    assert trained_model == mock_lgb_classifier_instance


@mock.patch("src.trading_platform.ai.training.pipeline.lgb")
@mock.patch("sklearn.ensemble.RandomForestClassifier")
@mock.patch("sklearn.model_selection.GridSearchCV")
@mock.patch("mlflow.log_params")
def test_aitp_train_model_lightgbm_with_tuning(
    mock_log_params, mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {
            "type": "lightgbm",
            "params": {"n_estimators": 50},
            "tuning": {
                "param_grid": {"n_estimators": [10, 20]},
                "settings": {"cv": 2},
            },
        },
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "lgbm_with_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    mock_grid_search_instance = mock_grid_search_cv.return_value
    mock_grid_search_instance.best_estimator_ = mock.Mock()
    mock_grid_search_instance.best_params_ = {"n_estimators": 20}

    trained_model = pipeline._train_model(X, y)

    mock_lgb.LGBMClassifier.assert_called_once_with(n_estimators=50)
    mock_grid_search_cv.assert_called_once_with(
        mock_lgb.LGBMClassifier.return_value,
        param_grid={"n_estimators": [10, 20]},
        cv=2,
    )
    mock_grid_search_instance.fit.assert_called_once_with(X, y)
    mock_log_params.assert_called_once_with({"n_estimators": 20})
    assert trained_model == mock_grid_search_instance.best_estimator_


@mock.patch("src.trading_platform.ai.training.pipeline.lgb")
@mock.patch("sklearn.ensemble.RandomForestClassifier")
@mock.patch("sklearn.model_selection.GridSearchCV")
def test_aitp_train_model_random_forest_no_tuning(
    mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "random_forest", "params": {"n_estimators": 50}},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "rf_no_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    mock_rf_classifier_instance = mock_rf_classifier.return_value
    trained_model = pipeline._train_model(X, y)

    mock_rf_classifier.assert_called_once_with(n_estimators=50)
    mock_rf_classifier_instance.fit.assert_called_once_with(X, y)
    mock_grid_search_cv.assert_not_called()
    assert trained_model == mock_rf_classifier_instance


@mock.patch("src.trading_platform.ai.training.pipeline.lgb")
@mock.patch("sklearn.ensemble.RandomForestClassifier")
@mock.patch("sklearn.model_selection.GridSearchCV")
@mock.patch("mlflow.log_params")
def test_aitp_train_model_random_forest_with_tuning(
    mock_log_params, mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {
            "type": "random_forest",
            "params": {"n_estimators": 50},
            "tuning": {
                "param_grid": {"n_estimators": [10, 20]},
                "settings": {"cv": 2},
            },
        },
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "rf_with_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    mock_grid_search_instance = mock_grid_search_cv.return_value
    mock_grid_search_instance.best_estimator_ = mock.Mock()
    mock_grid_search_instance.best_params_ = {"n_estimators": 20}

    trained_model = pipeline._train_model(X, y)

    mock_rf_classifier.assert_called_once_with(n_estimators=50)
    mock_grid_search_cv.assert_called_once_with(
        mock_rf_classifier.return_value,
        param_grid={"n_estimators": [10, 20]},
        cv=2,
    )
    mock_grid_search_instance.fit.assert_called_once_with(X, y)
    mock_log_params.assert_called_once_with({"n_estimators": 20})
    assert trained_model == mock_grid_search_instance.best_estimator_


def test_aitp_train_model_unsupported_type(mock_config_path):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "unsupported_model"},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "unsupported_model.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    with pytest.raises(ValueError, match="Unsupported model type: unsupported_model"):
        pipeline._train_model(X, y)


@mock.patch("src.trading_platform.ai.training.pipeline.lgb")
def test_aitp_train_model_lightgbm_import_error(mock_lgb, mock_config_path):
    mock_lgb.LGBMClassifier = None  # Simulate ImportError
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "lightgbm"},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "lgbm_import_error.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    with pytest.raises(ImportError, match="LightGBM is not installed or cannot be imported."):
        pipeline._train_model(X, y)


@mock.patch("src.trading_platform.ai.training.pipeline.AIEvaluationProcedure")
@mock.patch("mlflow.log_metrics")
@mock.patch("mlflow.sklearn.log_model")
@mock.patch("skl2onnx.convert_sklearn")
@mock.patch("mlflow.log_artifact")
@mock.patch("src.trading_platform.ai.training.pipeline.DiagnosticSynthesisEngine")
@mock.patch("json.loads")
@mock.patch("mlflow.log_dict")
@patch("os.remove")
def test_aitp_evaluate_and_log_artifacts(
    mock_os_remove,
    mock_log_dict,
    mock_json_loads,
    mock_synthesis_engine_cls,
    mock_log_artifact,
    mock_convert_sklearn,
    mock_log_model,
    mock_log_metrics,
    mock_eval_procedure_cls,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)
    mock_model = MagicMock()
    X = pd.DataFrame(np.random.rand(10, 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 2, 10))

    # Mock AIEvaluationProcedure
    mock_eval_procedure_instance = mock_eval_procedure_cls.return_value
    mock_eval_procedure_instance.run.return_value = {"accuracy": 0.9, "f1": 0.85}

    # Mock skl2onnx.convert_sklearn
    mock_onnx_model = MagicMock()
    mock_onnx_model.SerializeToString.return_value = b"dummy_onnx_model_bytes"
    mock_convert_sklearn.return_value = mock_onnx_model

    # Mock DiagnosticSynthesisEngine
    mock_synthesis_engine_instance = mock_synthesis_engine_cls.return_value
    mock_synthesis_engine_instance.generate_report_json.return_value = (
        '{"report": "test"}'
    )
    mock_json_loads.return_value = {"report": "test"}

    pipeline._evaluate_and_log_artifacts(mock_model, X, y)

    mock_eval_procedure_cls.assert_called_once_with(pipeline.config["evaluation"])
    mock_eval_procedure_instance.run.assert_called_once_with(mock_model, X, y)
    mock_log_metrics.assert_called_once_with({"accuracy": 0.9, "f1": 0.85})
    mock_log_model.assert_called_once_with(mock_model, "model")
    mock_convert_sklearn.assert_called_once()
    mock_log_artifact.assert_called_once_with(
        mock.ANY, artifact_path="model.onnx"
    )  # Check for path, content is mocked
    mock_synthesis_engine_cls.assert_called_once_with(mock.ANY)
    mock_synthesis_engine_instance.run.assert_called_once()
    mock_synthesis_engine_instance.generate_report_json.assert_called_once()
    mock_json_loads.assert_called_once_with('{"report": "test"}')
    mock_log_dict.assert_called_once_with(
        {"report": "test"}, "diagnostic_synthesis_results.json"
    )
    mock_os_remove.assert_called_once()


def test_flatten_dict_flat():
    d = {"a": 1, "b": "test"}
    assert _flatten_dict(d) == {"a": 1, "b": "test"}


def test_flatten_dict_nested_one_level():
    d = {"a": 1, "b": {"c": 2, "d": "hello"}}
    assert _flatten_dict(d) == {"a": 1, "b.c": 2, "b.d": "hello"}


def test_flatten_dict_nested_multiple_levels():
    d = {"a": 1, "b": {"c": 2, "d": {"e": 3, "f": "world"}}, "g": 4}
    expected = {"a": 1, "b.c": 2, "b.d.e": 3, "b.d.f": "world", "g": 4}
    assert _flatten_dict(d) == expected


def test_flatten_dict_empty():
    d = {}
    assert _flatten_dict(d) == {}


def test_flatten_dict_list_values():
    d = {"a": [1, 2], "b": {"c": [3, 4]}}
    expected = {"a": [1, 2], "b.c": [3, 4]}
    assert _flatten_dict(d) == expected


# --- Tests for AITrainingPipeline ---


@pytest.fixture
def mock_config_path(tmp_path):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "random_forest"},
        "evaluation": {},
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)
    return str(config_file)


@patch("mlflow.set_tracking_uri")
@patch("mlflow.set_experiment")
def test_aitp_init(mock_set_experiment, mock_set_tracking_uri, mock_config_path):
    pipeline = AITrainingPipeline(mock_config_path)
    assert pipeline.config["run_id"] == "test_run"
    assert pipeline.run_id == "test_run"
    mock_set_tracking_uri.assert_called_once_with("./mlruns_test")
    mock_set_experiment.assert_called_once_with("Test Experiment")


@patch("mlflow.set_tracking_uri")
@patch("mlflow.set_experiment")
def test_aitp_init_default_mlflow_settings(
    mock_set_experiment, mock_set_tracking_uri, tmp_path
):
    config_content = {
        "run_id": "test_run_default",
        "model": {"type": "random_forest"},
    }
    config_file = tmp_path / "config_default.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    assert pipeline.config["run_id"] == "test_run_default"
    mock_set_tracking_uri.assert_called_once_with("./mlruns")
    mock_set_experiment.assert_called_once_with("Default")


def test_aitp_load_config_success(mock_config_path):
    pipeline = AITrainingPipeline(mock_config_path)
    config = pipeline._load_config()
    assert config["run_id"] == "test_run"


def test_aitp_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        AITrainingPipeline("non_existent_config.yaml")


def test_aitp_load_config_invalid_yaml(tmp_path):
    invalid_config_file = tmp_path / "invalid.yaml"
    invalid_config_file.write_text("key: - value")  # Invalid YAML syntax
    with pytest.raises(yaml.YAMLError):
        AITrainingPipeline(str(invalid_config_file))


@patch("src.trading_platform.ai.data_connectors.AIDataConnector")
@patch("src.trading_platform.ai.data_labeling.DataLabeler")
@patch(
    "src.trading_platform.ai.feature_engineering.pipeline.FeatureEngineeringPipeline"
)
def test_aitp_load_and_prepare_data(
    mock_feature_pipeline_cls,
    mock_data_labeler_cls,
    mock_data_connector_cls,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)

    # Mock data connector
    mock_data_connector_instance = mock_data_connector_cls.return_value
    mock_data_connector_instance.load_training_data.return_value = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}
    )

    # Mock feature engineering pipeline
    mock_feature_pipeline_instance = mock_feature_pipeline_cls.return_value
    mock_feature_pipeline_instance.run.return_value = pd.DataFrame(
        {"feature1": [10], "feature2": [20]}, index=pd.to_datetime(["2023-01-01"])
    )

    # Mock data labeler
    mock_data_labeler_instance = mock_data_labeler_cls.return_value
    mock_data_labeler_instance.generate_future_price_direction.return_value = pd.Series(
        [1], index=pd.to_datetime(["2023-01-01"])
    )

    X, y = pipeline._load_and_prepare_data()

    mock_data_connector_cls.assert_called_once()
    mock_data_connector_instance.load_training_data.assert_called_once_with(
        symbol="TEST", timeframe="1H"
    )
    mock_feature_pipeline_cls.assert_called_once()
    mock_feature_pipeline_instance.run.assert_called_once()
    mock_data_labeler_cls.assert_called_once()
    mock_data_labeler_instance.generate_future_price_direction.assert_called_once()

    assert isinstance(X, pd.DataFrame)
    assert isinstance(y, pd.Series)
    assert X.shape == (1, 2)
    assert y.shape == (1,)
    assert X.index.equals(y.index)


@patch("src.trading_platform.ai.data_connectors.AIDataConnector")
@patch("src.trading_platform.ai.data_labeling.DataLabeler")
@patch(
    "src.trading_platform.ai.feature_engineering.pipeline.FeatureEngineeringPipeline"
)
def test_aitp_load_and_prepare_data_with_nans(
    mock_feature_pipeline_cls,
    mock_data_labeler_cls,
    mock_data_connector_cls,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)

    mock_data_connector_instance = mock_data_connector_cls.return_value
    mock_data_connector_instance.load_training_data.return_value = pd.DataFrame(
        {"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]}
    )

    mock_feature_pipeline_instance = mock_feature_pipeline_cls.return_value
    # Simulate NaNs in featured_df
    featured_df_with_nan = pd.DataFrame(
        {"feature1": [10, None], "feature2": [20, 30]},
        index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
    )
    mock_feature_pipeline_instance.run.return_value = featured_df_with_nan

    mock_data_labeler_instance = mock_data_labeler_cls.return_value
    labels = pd.Series([1, 0], index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
    mock_data_labeler_instance.generate_future_price_direction.return_value = labels

    X, y = pipeline._load_and_prepare_data()

    assert X.shape == (1, 2)  # NaN row should be dropped
    assert y.shape == (1,)
    assert X.index.equals(y.index)
    assert not X.isnull().any().any()
    assert not y.isnull().any()


@patch("src.trading_platform.ai.training.pipeline.lgb")
@patch("sklearn.ensemble.RandomForestClassifier")
@patch("sklearn.model_selection.GridSearchCV")
def test_aitp_train_model_lightgbm_no_tuning(
    mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "lightgbm", "params": {"n_estimators": 50}},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "lgbm_no_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    mock_lgbm_classifier_instance = mock_lgb.LGBMClassifier.return_value
    trained_model = pipeline._train_model(X, y)

    mock_lgb.LGBMClassifier.assert_called_once_with(n_estimators=50)
    mock_lgbm_classifier_instance.fit.assert_called_once_with(X, y)
    mock_grid_search_cv.assert_not_called()
    assert trained_model == mock_lgbm_classifier_instance


@patch("src.trading_platform.ai.training.pipeline.lgb")
@patch("sklearn.ensemble.RandomForestClassifier")
@patch("sklearn.model_selection.GridSearchCV")
@patch("mlflow.log_params")
def test_aitp_train_model_lightgbm_with_tuning(
    mock_log_params, mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {
            "type": "lightgbm",
            "params": {"n_estimators": 50},
            "tuning": {"param_grid": {"n_estimators": [10, 20]}, "settings": {"cv": 2}},
        },
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "lgbm_with_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    mock_grid_search_instance = mock_grid_search_cv.return_value
    mock_grid_search_instance.best_estimator_ = MagicMock()
    mock_grid_search_instance.best_params_ = {"n_estimators": 20}

    trained_model = pipeline._train_model(X, y)

    mock_lgb.LGBMClassifier.assert_called_once_with(n_estimators=50)
    mock_grid_search_cv.assert_called_once_with(
        mock_lgb.LGBMClassifier.return_value,
        param_grid={"n_estimators": [10, 20]},
        cv=2,
    )
    mock_grid_search_instance.fit.assert_called_once_with(X, y)
    mock_log_params.assert_called_once_with({"n_estimators": 20})
    assert trained_model == mock_grid_search_instance.best_estimator_


@patch("src.trading_platform.ai.training.pipeline.lgb")
@patch("sklearn.ensemble.RandomForestClassifier")
@patch("sklearn.model_selection.GridSearchCV")
def test_aitp_train_model_random_forest_no_tuning(
    mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "random_forest", "params": {"n_estimators": 50}},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "rf_no_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    mock_rf_classifier_instance = mock_rf_classifier.return_value
    trained_model = pipeline._train_model(X, y)

    mock_rf_classifier.assert_called_once_with(n_estimators=50)
    mock_rf_classifier_instance.fit.assert_called_once_with(X, y)
    mock_grid_search_cv.assert_not_called()
    assert trained_model == mock_rf_classifier_instance


@patch("src.trading_platform.ai.training.pipeline.lgb")
@patch("sklearn.ensemble.RandomForestClassifier")
@patch("sklearn.model_selection.GridSearchCV")
@patch("mlflow.log_params")
def test_aitp_train_model_random_forest_with_tuning(
    mock_log_params, mock_grid_search_cv, mock_rf_classifier, mock_lgb, mock_config_path
):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {
            "type": "random_forest",
            "params": {"n_estimators": 50},
            "tuning": {"param_grid": {"n_estimators": [10, 20]}, "settings": {"cv": 2}},
        },
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "rf_with_tuning.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    mock_grid_search_instance = mock_grid_search_cv.return_value
    mock_grid_search_instance.best_estimator_ = MagicMock()
    mock_grid_search_instance.best_params_ = {"n_estimators": 20}

    trained_model = pipeline._train_model(X, y)

    mock_rf_classifier.assert_called_once_with(n_estimators=50)
    mock_grid_search_cv.assert_called_once_with(
        mock_rf_classifier.return_value, param_grid={"n_estimators": [10, 20]}, cv=2
    )
    mock_grid_search_instance.fit.assert_called_once_with(X, y)
    mock_log_params.assert_called_once_with({"n_estimators": 20})
    assert trained_model == mock_grid_search_instance.best_estimator_


def test_aitp_train_model_unsupported_type(mock_config_path):
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "unsupported_model"},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "unsupported_model.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    with pytest.raises(ValueError, match="Unsupported model type: unsupported_model"):
        pipeline._train_model(X, y)


@patch("src.trading_platform.ai.training.pipeline.lgb")
def test_aitp_train_model_lightgbm_import_error(mock_lgb, mock_config_path):
    mock_lgb.LGBMClassifier = None  # Simulate ImportError
    config_content = {
        "run_id": "test_run",
        "experiment_name": "Test Experiment",
        "mlflow_tracking_uri": "./mlruns_test",
        "data": {"symbol": "TEST", "timeframe": "1H"},
        "features": [],
        "labeling": {},
        "model": {"type": "lightgbm"},
        "evaluation": {},
    }
    config_file = Path(mock_config_path).parent / "lgbm_import_error.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    pipeline = AITrainingPipeline(str(config_file))
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    with pytest.raises(ImportError, match="lightgbm is not installed."):
        pipeline._train_model(X, y)


@patch("src.trading_platform.ai.training.pipeline.AIEvaluationProcedure")
@patch("mlflow.log_metrics")
@patch("mlflow.sklearn.log_model")
@patch("skl2onnx.convert_sklearn")
@patch("mlflow.log_artifact")
@patch("src.trading_platform.ai.training.pipeline.DiagnosticSynthesisEngine")
@patch("json.loads")
@patch("mlflow.log_dict")
@patch("os.remove")
def test_aitp_evaluate_and_log_artifacts(
    mock_os_remove,
    mock_log_dict,
    mock_json_loads,
    mock_synthesis_engine_cls,
    mock_log_artifact,
    mock_convert_sklearn,
    mock_log_model,
    mock_log_metrics,
    mock_eval_procedure_cls,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)
    mock_model = MagicMock()
    X = pd.DataFrame({"f1": [1, 2], "f2": [3, 4]})
    y = pd.Series([0, 1])

    # Mock AIEvaluationProcedure
    mock_eval_procedure_instance = mock_eval_procedure_cls.return_value
    mock_eval_procedure_instance.run.return_value = {"accuracy": 0.9, "f1": 0.85}

    # Mock skl2onnx.convert_sklearn
    mock_onnx_model = MagicMock()
    mock_onnx_model.SerializeToString.return_value = b"dummy_onnx_model_bytes"
    mock_convert_sklearn.return_value = mock_onnx_model

    # Mock DiagnosticSynthesisEngine
    mock_synthesis_engine_instance = mock_synthesis_engine_cls.return_value
    mock_synthesis_engine_instance.generate_report_json.return_value = (
        '{"report": "test"}'
    )
    mock_json_loads.return_value = {"report": "test"}

    pipeline._evaluate_and_log_artifacts(mock_model, X, y)

    mock_eval_procedure_cls.assert_called_once_with(config={})
    mock_eval_procedure_instance.run.assert_called_once_with(mock_model, X, y)
    mock_log_metrics.assert_called_once_with({"accuracy": 0.9, "f1": 0.85})
    mock_log_model.assert_called_once_with(mock_model, "model")
    mock_convert_sklearn.assert_called_once()
    mock_log_artifact.assert_called_once_with("model.onnx", "onnx_model")
    mock_os_remove.assert_called_once_with("model.onnx")
    mock_synthesis_engine_cls.assert_called_once()
    mock_synthesis_engine_instance.run.assert_called_once()
    mock_synthesis_engine_instance.generate_report_json.assert_called_once()
    mock_json_loads.assert_called_once_with('{"report": "test"}')
    mock_log_dict.assert_called_once_with(
        {"report": "test"}, "diagnostic_synthesis_results.json"
    )


@patch("mlflow.start_run")
@patch.object(AITrainingPipeline, "_load_and_prepare_data")
@patch.object(AITrainingPipeline, "_train_model")
@patch.object(AITrainingPipeline, "_evaluate_and_log_artifacts")
@patch("mlflow.log_params")
def test_aitp_run(
    mock_log_params,
    mock_evaluate_and_log_artifacts,
    mock_train_model,
    mock_load_and_prepare_data,
    mock_start_run,
    mock_config_path,
):
    pipeline = AITrainingPipeline(mock_config_path)

    mock_run_context = MagicMock()
    mock_run_context.info.run_id = "mock_run_id"
    mock_start_run.return_value.__enter__.return_value = mock_run_context

    mock_load_and_prepare_data.return_value = (pd.DataFrame(), pd.Series())
    mock_train_model.return_value = MagicMock()

    pipeline.run()

    mock_start_run.assert_called_once_with(run_name="test_run")
    mock_log_params.assert_called_once()
    mock_load_and_prepare_data.assert_called_once()
    mock_train_model.assert_called_once()
    mock_evaluate_and_log_artifacts.assert_called_once()
