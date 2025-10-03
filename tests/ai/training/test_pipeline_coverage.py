# ruff: noqa

"""
Test coverage for trading_platform.ai.training.pipeline module.
This test file focuses on achieving 100% coverage by mocking external dependencies
that cause import issues.
"""

import json
import tempfile
import unittest.mock as mock
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, cast
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def mock_pipeline_modules(monkeypatch):
    """Install lightweight module stubs for heavy training dependencies."""

    import sys

    mlflow_module = ModuleType("mlflow")

    def _noop(*_, **__):
        return None

    setattr(mlflow_module, "set_tracking_uri", _noop)
    setattr(mlflow_module, "set_experiment", _noop)
    setattr(mlflow_module, "log_params", _noop)
    setattr(mlflow_module, "log_metrics", _noop)
    setattr(mlflow_module, "log_artifact", _noop)
    setattr(mlflow_module, "log_dict", _noop)

    def _start_run(*_, **__):
        class _RunContext:
            def __enter__(self):
                return SimpleNamespace(info=SimpleNamespace(run_id="mock"))

            def __exit__(self, exc_type, exc, tb):
                return False

        return _RunContext()

    setattr(mlflow_module, "start_run", _start_run)

    mlflow_sklearn = ModuleType("mlflow.sklearn")

    def _log_model(*_, **__):
        return SimpleNamespace(model_uri="mock")

    setattr(mlflow_sklearn, "log_model", _log_model)
    setattr(mlflow_module, "sklearn", mlflow_sklearn)

    sklearn_module = ModuleType("sklearn")

    sklearn_metrics = ModuleType("sklearn.metrics")

    def _fake_metric(*_, **__):
        return 0.5

    setattr(sklearn_metrics, "accuracy_score", MagicMock(side_effect=_fake_metric))
    setattr(sklearn_metrics, "f1_score", MagicMock(side_effect=_fake_metric))
    setattr(
        sklearn_metrics,
        "precision_score",
        MagicMock(side_effect=_fake_metric),
    )
    setattr(sklearn_metrics, "recall_score", MagicMock(side_effect=_fake_metric))
    setattr(sklearn_metrics, "roc_auc_score", MagicMock(side_effect=_fake_metric))

    sklearn_ensemble = ModuleType("sklearn.ensemble")

    class _RFClassifier:
        def __init__(self, *_, **__):
            self.fit_called = False

        def fit(self, *_, **__):
            self.fit_called = True
            return self

    setattr(sklearn_ensemble, "RandomForestClassifier", _RFClassifier)

    sklearn_model_selection = ModuleType("sklearn.model_selection")

    class _GridSearch:
        def __init__(self, *_, **__):
            self.best_estimator_ = _RFClassifier()
            self.best_params_ = {}

        def fit(self, *_, **__):
            return None

    class _TimeSeriesSplit:
        def __init__(self, *_, **__):
            pass

        def split(self, *_):
            return []

    setattr(sklearn_model_selection, "GridSearchCV", _GridSearch)
    setattr(sklearn_model_selection, "TimeSeriesSplit", _TimeSeriesSplit)

    setattr(sklearn_module, "metrics", sklearn_metrics)
    setattr(sklearn_module, "ensemble", sklearn_ensemble)
    setattr(sklearn_module, "model_selection", sklearn_model_selection)

    skl2onnx_module = ModuleType("skl2onnx")

    def _convert_sklearn(*_, **__):
        class _ONNX:
            def SerializeToString(self):
                return b""

        return _ONNX()

    setattr(skl2onnx_module, "convert_sklearn", _convert_sklearn)

    skl2onnx_common = ModuleType("skl2onnx.common")
    skl2onnx_common_data_types = ModuleType("skl2onnx.common.data_types")

    class _FloatTensorType:
        def __init__(self, *_):
            pass

    setattr(skl2onnx_common_data_types, "FloatTensorType", _FloatTensorType)
    setattr(skl2onnx_common, "data_types", skl2onnx_common_data_types)
    setattr(skl2onnx_module, "common", skl2onnx_common)

    scipy_module = ModuleType("scipy")
    scipy_stats = ModuleType("scipy.stats")

    def _ttest_ind(*_, **__):
        class _Result:
            statistic = 0.0
            pvalue = 1.0

        return _Result()

    setattr(scipy_stats, "ttest_ind", _ttest_ind)
    setattr(scipy_module, "stats", scipy_stats)

    eval_metrics = ModuleType("trading_platform.ai.evaluation.metrics")

    def _get_classification_metrics(*_, **__):
        return {"accuracy": 1.0}

    setattr(eval_metrics, "get_classification_metrics", _get_classification_metrics)

    eval_procedure = ModuleType("trading_platform.ai.evaluation.procedure")

    class _StubProcedure:
        def __init__(self, config=None):
            self.config = config or {}

        def run(self, *_args, **_kwargs):
            return {"accuracy": 0.5}

    setattr(eval_procedure, "AIEvaluationProcedure", _StubProcedure)

    modules = {
        "mlflow": mlflow_module,
        "mlflow.sklearn": mlflow_sklearn,
        "sklearn": sklearn_module,
        "sklearn.metrics": sklearn_metrics,
        "sklearn.ensemble": sklearn_ensemble,
        "sklearn.model_selection": sklearn_model_selection,
        "skl2onnx": skl2onnx_module,
        "skl2onnx.common": skl2onnx_common,
        "skl2onnx.common.data_types": skl2onnx_common_data_types,
        "scipy": scipy_module,
        "scipy.stats": scipy_stats,
        "trading_platform.ai.evaluation.metrics": eval_metrics,
        "trading_platform.ai.evaluation.procedure": eval_procedure,
    }

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    # Ensure training pipeline picks up the stubbed modules
    import importlib

    if "trading_platform.ai.training.pipeline" in sys.modules:
        importlib.reload(sys.modules["trading_platform.ai.training.pipeline"])

    yield modules


def test_import_pipeline_without_lightgbm(monkeypatch, mock_pipeline_modules):
    """Ensure pipeline falls back when lightgbm import fails."""
    import importlib
    import sys
    from builtins import __import__ as real_import

    monkeypatch.delitem(
        sys.modules,
        "trading_platform.ai.training.pipeline",
        raising=False,
    )

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "lightgbm":
            raise ImportError("Mock missing lightgbm")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    module = importlib.import_module("trading_platform.ai.training.pipeline")
    assert module.lgb is None
    monkeypatch.delitem(
        sys.modules,
        "trading_platform.ai.training.pipeline",
        raising=False,
    )


@pytest.mark.usefixtures("mock_pipeline_modules")
class TestAITrainingPipelineImports:
    """Test imports and basic instantiation."""

    def test_import_pipeline_module(self):
        """Test that the pipeline module can be imported with mocked dependencies."""
        from trading_platform.ai.training.pipeline import (
            AITrainingPipeline,
            _flatten_dict,
        )

        assert AITrainingPipeline is not None
        assert _flatten_dict is not None


@pytest.mark.usefixtures("mock_pipeline_modules")
class TestFlattenDict:
    """Test the _flatten_dict utility function."""

    def test_flatten_dict_nested(self):
        """Test flattening nested dictionary."""
        from trading_platform.ai.training.pipeline import _flatten_dict

        nested = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
        expected = {"a": 1, "b.c": 2, "b.d.e": 3}
        result = _flatten_dict(nested)
        assert result == expected

    def test_flatten_dict_flat(self):
        """Test flattening already flat dictionary."""
        from trading_platform.ai.training.pipeline import _flatten_dict

        flat = {"a": 1, "b": 2}
        result = _flatten_dict(flat)
        assert result == flat


@pytest.mark.usefixtures("mock_pipeline_modules")
class TestAITrainingPipeline:
    """Test AITrainingPipeline class with comprehensive mocking."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock configuration file."""
        from trading_platform.core import paths

        config = {
            "run_id": "test_run",
            "experiment_name": "Test Experiment",
            "mlflow_tracking_uri": paths.MLFLOW_TEST_URI,
            "data": {
                "symbol": "EURUSD",
                "timeframe": "1D",
                "start_date": "2023-01-01",
                "end_date": "2023-06-30",
            },
            "features": [{"kind": "sma", "length": 10}],
            "labeling": {"look_ahead_bars": 5},
            "model": {
                "type": "random_forest",
                "params": {"n_estimators": 10, "random_state": 42},
            },
            "evaluation": {
                "run_cross_validation": True,
                "cross_validation": {"n_splits": 3},
            },
            "synthesis": {"enable": True},
        }
        config_file = tmp_path / "test_config.yaml"

        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        return str(config_file)

    def test_init_loads_config(self, mock_config):
        """Test AITrainingPipeline initialization and config loading."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        with patch("mlflow.set_tracking_uri") as mock_set_uri, patch(
            "mlflow.set_experiment"
        ) as mock_set_exp:
            pipeline = AITrainingPipeline(mock_config)
            assert pipeline.config_path == Path(mock_config)
            assert pipeline.run_id == "test_run"
            assert "data" in pipeline.config

            # Test MLflow setup calls
            from trading_platform.core import paths

            mock_set_uri.assert_called_once_with(paths.MLFLOW_TEST_URI)
            mock_set_exp.assert_called_once_with("Test Experiment")

    def test_load_config_missing_defaults(self, tmp_path):
        """Test config loading with missing optional fields - covers lines 31-32."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline
        from trading_platform.core import paths

        # Config without run_id and mlflow settings
        config = {"data": {"symbol": "EURUSD"}, "model": {"type": "random_forest"}}

        config_file = tmp_path / "minimal_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        with patch("mlflow.set_tracking_uri") as mock_set_uri, patch(
            "mlflow.set_experiment"
        ) as mock_set_exp:
            pipeline = AITrainingPipeline(str(config_file))

            # Test default values - covers lines 31-32
            assert pipeline.run_id == "default_run"
            mock_set_uri.assert_called_once_with(paths.MLFLOW_DEFAULT_URI)
            mock_set_exp.assert_called_once_with("Default")

    @patch("trading_platform.ai.training.pipeline.AIDataConnector")
    @patch("trading_platform.ai.training.pipeline.DataCatalog")
    @patch("trading_platform.ai.training.pipeline.FeatureEngineeringPipeline")
    @patch("trading_platform.ai.training.pipeline.DataLabeler")
    def test_load_and_prepare_data(
        self,
        mock_labeler_cls,
        mock_fe_cls,
        mock_catalog_cls,
        mock_connector_cls,
        mock_config,
    ):
        """Test data loading and preparation - covers lines 129."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        raw_df = pd.DataFrame({"price": [1, 2, 3], "volume": [100, 200, 300]})
        labels = pd.Series([0, 1, 0], index=[0, 1, 2], name="label")

        mock_connector = MagicMock()
        mock_connector.load_training_data.return_value = raw_df
        mock_connector_cls.return_value = mock_connector

        subset_df = MagicMock()
        subset_df.index = labels.index
        subset_df.dropna.return_value = None
        subset_df.shape = (3, 3)

        featured_df = MagicMock()
        featured_df.shape = (3, 3)
        locator = MagicMock()
        locator.__getitem__.return_value = subset_df
        featured_df.loc = locator

        mock_fe_pipeline = MagicMock()
        mock_fe_pipeline.run.return_value = featured_df
        mock_fe_cls.return_value = mock_fe_pipeline

        mock_labeler = MagicMock()
        mock_labeler.generate_future_price_direction.return_value = labels
        mock_labeler_cls.return_value = mock_labeler

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"):
            pipeline = AITrainingPipeline(mock_config)
            X, y = pipeline._load_and_prepare_data()

        mock_connector.load_training_data.assert_called_once()
        mock_fe_pipeline.run.assert_called_once()
        mock_labeler.generate_future_price_direction.assert_called_once_with(
            featured_df
        )
        assert X is subset_df
        assert y.equals(labels)

    def test_train_model_random_forest(self, mock_config):
        """Test model training with random forest - covers model creation logic."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        X = pd.DataFrame({"feature1": [1, 2, 3], "feature2": [4, 5, 6]})
        y = pd.Series([0, 1, 0])

        # Mock RandomForestClassifier
        mock_model = MagicMock()
        mock_model.fit.return_value = None

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"), patch(
            "trading_platform.ai.training.pipeline.RandomForestClassifier",
            return_value=mock_model,
        ):
            pipeline = AITrainingPipeline(mock_config)
            trained_model = pipeline._train_model(X, y)

            assert trained_model == mock_model
            mock_model.fit.assert_called_once_with(X, y)

    def test_train_model_lightgbm(self, mock_config, tmp_path):
        """Test model training with LightGBM - covers LightGBM branch."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        # Modify config for LightGBM
        config = {
            "run_id": "test_run",
            "model": {
                "type": "lightgbm",
                "params": {"n_estimators": 10, "random_state": 42},
            },
        }

        config_file = tmp_path / "lgb_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        X = pd.DataFrame({"feature1": [1, 2, 3], "feature2": [4, 5, 6]})
        y = pd.Series([0, 1, 0])

        # Mock LightGBM
        mock_lgb_model = MagicMock()
        mock_lgb_model.fit.return_value = None
        mock_lgb_cls = MagicMock(return_value=mock_lgb_model)

        # Mock lgb module
        mock_lgb_module = MagicMock()
        mock_lgb_module.LGBMClassifier = mock_lgb_cls

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"), patch(
            "trading_platform.ai.training.pipeline.lgb", mock_lgb_module
        ):
            pipeline = AITrainingPipeline(str(config_file))
            trained_model = pipeline._train_model(X, y)

            assert trained_model == mock_lgb_model
            mock_lgb_cls.assert_called_once_with(n_estimators=10, random_state=42)
            mock_lgb_model.fit.assert_called_once_with(X, y)

    def test_train_model_lightgbm_import_error(self, mock_config, tmp_path):
        """Test LightGBM import error handling - covers lines 164-173."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        # Modify config for LightGBM
        config = {"run_id": "test_run", "model": {"type": "lightgbm"}}

        config_file = tmp_path / "lgb_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        X = pd.DataFrame({"feature1": [1, 2, 3]})
        y = pd.Series([0, 1, 0])

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"), patch(
            "trading_platform.ai.training.pipeline.lgb", None
        ):  # lgb is None
            pipeline = AITrainingPipeline(str(config_file))

            # Should raise ImportError when lgb is None - covers lines 164-173
            with pytest.raises(ImportError, match="LightGBM is not installed"):
                pipeline._train_model(X, y)

    def test_train_model_unsupported_type(self, mock_config, tmp_path):
        """Test unsupported model type error."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        # Config with unsupported model type
        config = {"run_id": "test_run", "model": {"type": "unsupported_model"}}

        config_file = tmp_path / "bad_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        X = pd.DataFrame({"feature1": [1, 2, 3]})
        y = pd.Series([0, 1, 0])

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"):
            pipeline = AITrainingPipeline(str(config_file))

            with pytest.raises(ValueError, match="Unsupported model type"):
                pipeline._train_model(X, y)

    def test_train_model_with_tuning(self, mock_config, tmp_path):
        """Test model training with hyperparameter tuning."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        # Config with tuning settings
        config = {
            "run_id": "test_run",
            "model": {
                "type": "random_forest",
                "params": {"random_state": 42},
                "tuning": {
                    "param_grid": {"n_estimators": [10, 20]},
                    "settings": {"cv": 3},
                },
            },
        }

        config_file = tmp_path / "tuning_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        X = pd.DataFrame({"feature1": [1, 2, 3], "feature2": [4, 5, 6]})
        y = pd.Series([0, 1, 0])

        # Mock GridSearchCV and model
        mock_model = MagicMock()
        mock_grid = MagicMock()
        mock_grid.fit.return_value = None
        mock_grid.best_estimator_ = mock_model
        mock_grid.best_params_ = {"n_estimators": 20}

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"), patch(
            "trading_platform.ai.training.pipeline.RandomForestClassifier"
        ), patch(
            "trading_platform.ai.training.pipeline.GridSearchCV", return_value=mock_grid
        ), patch("mlflow.log_params") as mock_log_params:
            pipeline = AITrainingPipeline(str(config_file))
            trained_model = pipeline._train_model(X, y)

            assert trained_model == mock_model
            mock_grid.fit.assert_called_once_with(X, y)
            mock_log_params.assert_called_once_with({"n_estimators": 20})

    @patch("trading_platform.ai.training.pipeline.AIEvaluationProcedure")
    @patch("trading_platform.ai.training.pipeline.DiagnosticSynthesisEngine")
    def test_evaluate_and_log_artifacts(
        self, mock_synthesis_cls, mock_eval_cls, mock_config
    ):
        """Test evaluation and artifact logging - covers lines 262."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        X = pd.DataFrame({"feature1": [1, 2, 3]})
        y = pd.Series([0, 1, 0])
        mock_model = MagicMock()

        # Setup evaluation mocks
        mock_evaluator = MagicMock()
        mock_evaluator.run.return_value = {"accuracy": 0.85, "nested": {"f1": 0.80}}
        mock_eval_cls.return_value = mock_evaluator

        # Setup synthesis mocks
        mock_synthesis = MagicMock()
        mock_synthesis.run.return_value = None
        mock_synthesis.generate_report_json.return_value = '{"insights": ["test"]}'
        mock_synthesis_cls.return_value = mock_synthesis

        # Setup ONNX and MLflow mocks
        mock_onnx_model = MagicMock()
        mock_onnx_model.SerializeToString.return_value = b"onnx_bytes"
        mock_model_info = MagicMock()
        mock_model_info.model_uri = "models:/test_model/1"

        config_text = Path(mock_config).read_text()

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"), patch(
            "mlflow.log_metrics"
        ) as mock_log_metrics, patch(
            "mlflow.sklearn.log_model", return_value=mock_model_info
        ) as mock_log_model, patch(
            "trading_platform.ai.training.pipeline.convert_sklearn",
            return_value=mock_onnx_model,
        ) as mock_convert, patch("mlflow.log_artifact") as mock_log_artifact, patch(
            "mlflow.log_dict"
        ) as mock_log_dict, patch(
            "builtins.open", mock.mock_open(read_data=config_text)
        ) as mock_file, patch("os.remove") as mock_remove:
            pipeline = AITrainingPipeline(mock_config)
            pipeline._evaluate_and_log_artifacts(mock_model, X, y)

            # Verify evaluation
            mock_evaluator.run.assert_called_once_with(mock_model, X, y)
            mock_log_metrics.assert_called_once_with(
                {"accuracy": 0.85, "nested.f1": 0.80}
            )

            # Verify model logging
            mock_log_model.assert_called_once_with(mock_model, "model")

            # Verify ONNX conversion and logging - covers line 262
            mock_convert.assert_called_once()
            mock_log_artifact.assert_called_once_with("model.onnx", "onnx_model")
            mock_remove.assert_called_once_with("model.onnx")

            # Verify synthesis engine
            mock_synthesis.run.assert_called_once()
            mock_synthesis.generate_report_json.assert_called_once()
            mock_log_dict.assert_called_once_with(
                {"insights": ["test"]}, "diagnostic_synthesis_results.json"
            )

    def test_evaluate_and_log_artifacts_with_default_stubs(self, mock_config):
        """Exercise evaluation branch using the fixture stubs."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        pipeline = AITrainingPipeline(mock_config)
        model = MagicMock()

        subset_df = MagicMock()
        subset_df.index = pd.RangeIndex(3)
        subset_df.shape = (3, 2)
        subset_df.dropna.return_value = None

        y = pd.Series([0, 1, 0])

        with patch("mlflow.log_metrics") as mock_log_metrics, patch(
            "mlflow.sklearn.log_model",
            return_value=SimpleNamespace(model_uri="mlflow://model"),
        ) as mock_log_model, patch(
            "trading_platform.ai.training.pipeline.convert_sklearn"
        ) as mock_convert, patch("mlflow.log_artifact") as mock_log_artifact, patch(
            "mlflow.log_dict"
        ) as mock_log_dict, patch("builtins.open", mock.mock_open()), patch(
            "os.remove"
        ):
            mock_convert.return_value.SerializeToString.return_value = b"onnx"
            pipeline._evaluate_and_log_artifacts(model, subset_df, y)

        mock_log_metrics.assert_called_once()
        mock_log_model.assert_called_once()
        mock_log_artifact.assert_called_once_with("model.onnx", "onnx_model")
        mock_log_dict.assert_called_once()

    def test_evaluate_artifacts_without_eval_config(self, mock_config):
        """Ensure metrics logging is skipped when evaluation config is empty."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        pipeline = AITrainingPipeline(mock_config)
        pipeline.config["evaluation"] = {}
        dummy_model = MagicMock()
        X = pd.DataFrame({"feature1": [1.0], "feature2": [2.0]})
        y = pd.Series([0])

        with patch("mlflow.sklearn.log_model") as mock_log_model, patch(
            "trading_platform.ai.training.pipeline.convert_sklearn"
        ) as mock_convert, patch("mlflow.log_artifact") as mock_log_artifact, patch(
            "mlflow.log_dict"
        ) as mock_log_dict, patch(
            "trading_platform.ai.training.pipeline.DiagnosticSynthesisEngine"
        ) as mock_synth, patch("mlflow.log_metrics") as mock_log_metrics, patch(
            "builtins.open", mock.mock_open()
        ), patch("os.remove"):
            mock_convert.return_value = SimpleNamespace(SerializeToString=lambda: b"")
            synth_instance = MagicMock()
            synth_instance.generate_report_json.return_value = "{}"
            mock_synth.return_value = synth_instance

            pipeline._evaluate_and_log_artifacts(dummy_model, X, y)

        mock_log_metrics.assert_not_called()
        mock_log_model.assert_called_once_with(dummy_model, "model")
        mock_log_artifact.assert_called_once_with("model.onnx", "onnx_model")
        mock_log_dict.assert_called_once_with({}, "diagnostic_synthesis_results.json")

    @patch("trading_platform.ai.training.pipeline.AIDataConnector")
    @patch("trading_platform.ai.training.pipeline.DataCatalog")
    @patch("trading_platform.ai.training.pipeline.FeatureEngineeringPipeline")
    @patch("trading_platform.ai.training.pipeline.DataLabeler")
    @patch("trading_platform.ai.training.pipeline.AIEvaluationProcedure")
    @patch("trading_platform.ai.training.pipeline.DiagnosticSynthesisEngine")
    def test_full_pipeline_run(
        self,
        mock_synthesis_cls,
        mock_eval_cls,
        mock_labeler_cls,
        mock_fe_cls,
        mock_catalog_cls,
        mock_connector_cls,
        mock_config,
    ):
        """Test full pipeline run method."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        # Setup all mocks for a complete run
        raw_df = pd.DataFrame({"price": [1, 2, 3]})
        labels = pd.Series([0, 1, 0], index=[0, 1, 2])

        mock_connector = MagicMock()
        mock_connector.load_training_data.return_value = raw_df
        mock_connector_cls.return_value = mock_connector

        subset_df = MagicMock()
        subset_df.index = labels.index
        subset_df.dropna.return_value = None
        subset_df.shape = (3, 2)

        featured_df = MagicMock()
        featured_df.shape = (3, 2)
        locator = MagicMock()
        locator.__getitem__.return_value = subset_df
        featured_df.loc = locator

        mock_fe_pipeline = MagicMock()
        mock_fe_pipeline.run.return_value = featured_df
        mock_fe_cls.return_value = mock_fe_pipeline

        mock_labeler = MagicMock()
        mock_labeler.generate_future_price_direction.return_value = labels
        mock_labeler_cls.return_value = mock_labeler

        mock_evaluator = MagicMock()
        mock_evaluator.run.return_value = {"accuracy": 0.85}
        mock_eval_cls.return_value = mock_evaluator

        mock_synthesis = MagicMock()
        mock_synthesis.run.return_value = None
        mock_synthesis.generate_report_json.return_value = '{"test": true}'
        mock_synthesis_cls.return_value = mock_synthesis

        mock_model = MagicMock()
        mock_onnx_model = MagicMock()
        mock_onnx_model.SerializeToString.return_value = b"test"
        mock_model_info = MagicMock()

        config_text = Path(mock_config).read_text()

        with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"), patch(
            "mlflow.start_run"
        ) as mock_start_run, patch("mlflow.log_params"), patch(
            "mlflow.log_metrics"
        ), patch("mlflow.sklearn.log_model", return_value=mock_model_info), patch(
            "trading_platform.ai.training.pipeline.RandomForestClassifier",
            return_value=mock_model,
        ), patch(
            "trading_platform.ai.training.pipeline.convert_sklearn",
            return_value=mock_onnx_model,
        ), patch("mlflow.log_artifact"), patch("mlflow.log_dict"), patch(
            "builtins.open", mock.mock_open(read_data=config_text)
        ), patch("os.remove"):
            mock_run_context = MagicMock()
            mock_run_context.info.run_id = "test_run_123"
            mock_start_run.return_value.__enter__.return_value = mock_run_context

            pipeline = AITrainingPipeline(mock_config)
            pipeline.run()

        # Verify MLflow run was started
        mock_start_run.assert_called_once_with(run_name="test_run")

    def test_run_invokes_components(self, mock_config, monkeypatch):
        """Ensure run orchestrates component helpers."""
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        pipeline = AITrainingPipeline(mock_config)

        dummy_X = MagicMock()
        dummy_y = MagicMock()

        pipeline_any = cast(Any, pipeline)
        load_mock = MagicMock(return_value=(dummy_X, dummy_y))
        train_mock = MagicMock(return_value="trained_model")
        eval_mock = MagicMock()
        pipeline_any._load_and_prepare_data = load_mock
        pipeline_any._train_model = train_mock
        pipeline_any._evaluate_and_log_artifacts = eval_mock

        with patch("mlflow.start_run") as mock_start_run, patch("mlflow.log_params"):
            context = SimpleNamespace(info=SimpleNamespace(run_id="stub"))
            mock_start_run.return_value.__enter__.return_value = context
            pipeline.run()

        load_mock.assert_called_once_with()
        train_mock.assert_called_once_with(dummy_X, dummy_y)
        eval_mock.assert_called_once_with("trained_model", dummy_X, dummy_y)

    def test_main_function(self, tmp_path):
        """Test main function execution - covers main() function."""
        from trading_platform.ai.training.pipeline import main

        # Mock all the heavy dependencies
        with patch(
            "trading_platform.ai.training.pipeline.AITrainingPipeline"
        ) as mock_pipeline_cls, patch(
            "builtins.open", mock.mock_open()
        ) as mock_file, patch("yaml.dump") as mock_yaml_dump:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = None
            mock_pipeline_cls.return_value = mock_pipeline

            # Change working directory to tmp_path to avoid file conflicts
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)
                main()
            finally:
                os.chdir(original_cwd)

            # Verify config file was created and pipeline was instantiated and run
            mock_file.assert_called()
            mock_yaml_dump.assert_called_once()
            mock_pipeline_cls.assert_called_once()
            mock_pipeline.run.assert_called_once()

    def test_module_entry_point_guard(self, monkeypatch):
        """Execute module as script while stubbing heavy collaborators."""
        import runpy
        import sys
        import yaml

        module_name = "trading_platform.ai.training.pipeline"
        monkeypatch.delitem(sys.modules, module_name, raising=False)

        from trading_platform.core import paths

        config = {
            "run_id": "guard_run",
            "experiment_name": "Guard",
            "mlflow_tracking_uri": paths.MLFLOW_DEFAULT_URI,
            "data": {"symbol": "EURUSD"},
            "features": [],
            "labeling": {},
            "model": {"type": "random_forest", "params": {}},
            "evaluation": {},
        }
        config_text = yaml.safe_dump(config)

        with patch(
            "builtins.open", mock.mock_open(read_data=config_text)
        ) as mock_file, patch("yaml.dump") as mock_yaml_dump, patch(
            "trading_platform.ai.data_connectors.AIDataConnector"
        ) as mock_connector_cls, patch(
            "trading_platform.ai.data_connectors.DataCatalog"
        ) as mock_catalog_cls, patch(
            "trading_platform.ai.feature_engineering.pipeline."
            "FeatureEngineeringPipeline"
        ) as mock_fe_cls, patch(
            "trading_platform.ai.data_labeling.DataLabeler"
        ) as mock_labeler_cls, patch(
            "trading_platform.ai.synthesis.engine.DiagnosticSynthesisEngine"
        ) as mock_synth_cls, patch("os.remove"):
            mock_catalog_cls.return_value = MagicMock()

            raw_df = pd.DataFrame({"feature1": [1.0], "feature2": [2.0]})
            labels = pd.Series([0], index=[0], name="label")

            mock_connector = MagicMock()
            mock_connector.load_training_data.return_value = raw_df
            mock_connector_cls.return_value = mock_connector

            subset_df = raw_df.copy()
            locator = MagicMock()
            locator.__getitem__.return_value = subset_df

            featured_df = MagicMock()
            featured_df.shape = subset_df.shape
            featured_df.loc = locator

            mock_fe_pipeline = MagicMock()
            mock_fe_pipeline.run.return_value = featured_df
            mock_fe_cls.return_value = mock_fe_pipeline

            mock_labeler = MagicMock()
            mock_labeler.generate_future_price_direction.return_value = labels
            mock_labeler_cls.return_value = mock_labeler

            mock_synth = MagicMock()
            mock_synth.run.return_value = None
            mock_synth.generate_report_json.return_value = "{}"
            mock_synth_cls.return_value = mock_synth

            runpy.run_module(module_name, run_name="__main__", alter_sys=True)

        mock_file.assert_called()
        mock_yaml_dump.assert_called_once()
