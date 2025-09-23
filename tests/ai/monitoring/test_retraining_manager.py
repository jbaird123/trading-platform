from unittest.mock import patch

import pandas as pd
import pytest
from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager


@pytest.fixture
def mock_retraining_manager():
    mock_config = {
        "retraining_criteria": {
            "on_data_drift": True,
            "on_concept_drift": True,
            "on_performance_degradation": True,
            "min_sharpe_for_retraining": 0.5,
            "scheduled_interval": None,
        },
        "drift_detector_config": {},
        "performance_monitor_config": {},
    }
    return AIRetrainingManager(mock_config)


@pytest.fixture
def dummy_data():
    return pd.DataFrame({"feature": [1, 2, 3]}), pd.Series([0, 1, 0])


@pytest.fixture
def dummy_brief():
    return {"overall_performance": {"sharpe_ratio": 0.6}}


class TestAIRetrainingManager:
    def test_initialization(self, mock_retraining_manager):
        assert isinstance(mock_retraining_manager, AIRetrainingManager)
        assert mock_retraining_manager.config is not None
        assert mock_retraining_manager.drift_detector is not None
        assert mock_retraining_manager.performance_monitor is not None

    @patch(
        "trading_platform.ai.monitoring.performance_monitor.AIDriftDetector.check_for_drift"
    )
    def test_evaluate_retraining_need_data_drift(
        self,
        mock_check_for_drift,
        mock_retraining_manager,
        dummy_data,
        dummy_brief,
    ):
        mock_check_for_drift.return_value = {
            "data_drift_detected": True,
            "concept_drift_detected": False,
        }
        mock_retraining_manager.retraining_criteria = {
            "on_data_drift": True,
            "on_concept_drift": False,
        }
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief,
        )
        assert needed is True

    @patch(
        "trading_platform.ai.monitoring.performance_monitor.AIDriftDetector.check_for_drift"
    )
    def test_evaluate_retraining_need_concept_drift(
        self,
        mock_check_for_drift,
        mock_retraining_manager,
        dummy_data,
        dummy_brief,
    ):
        mock_check_for_drift.return_value = {
            "data_drift_detected": False,
            "concept_drift_detected": True,
        }
        mock_retraining_manager.retraining_criteria = {
            "on_data_drift": False,
            "on_concept_drift": True,
        }
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief,
        )
        assert needed is True

    @patch(
        "trading_platform.ai.monitoring.performance_monitor.AIDriftDetector.check_for_drift"
    )
    def test_evaluate_retraining_need_both_drifts(
        self,
        mock_check_for_drift,
        mock_retraining_manager,
        dummy_data,
        dummy_brief,
    ):
        mock_check_for_drift.return_value = {
            "data_drift_detected": True,
            "concept_drift_detected": True,
        }
        mock_retraining_manager.retraining_criteria = {
            "on_data_drift": True,
            "on_concept_drift": True,
        }
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief,
        )
        assert needed is True

    @patch(
        "trading_platform.ai.monitoring.performance_monitor.AIDriftDetector.check_for_drift"
    )
    def test_evaluate_retraining_need_no_drift_criteria(
        self,
        mock_check_for_drift,
        mock_retraining_manager,
        dummy_data,
        dummy_brief,
    ):
        mock_check_for_drift.return_value = {
            "data_drift_detected": True,
            "concept_drift_detected": True,
        }
        mock_retraining_manager.retraining_criteria = {
            "on_data_drift": False,
            "on_concept_drift": False,
        }
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief,
        )
        assert needed is False

    def test_evaluate_retraining_need_performance_degradation(
        self, mock_retraining_manager, dummy_data
    ):
        mock_retraining_manager.retraining_criteria = {
            "on_performance_degradation": True,
            "min_sharpe_for_retraining": 0.5,
        }
        dummy_brief_degraded = {"overall_performance": {"sharpe_ratio": 0.4}}
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief_degraded,
        )
        assert needed is True

    def test_evaluate_retraining_need_performance_ok(
        self, mock_retraining_manager, dummy_data
    ):
        mock_retraining_manager.retraining_criteria = {
            "on_performance_degradation": True,
            "min_sharpe_for_retraining": 0.9,
        }
        dummy_brief_ok = {"overall_performance": {"sharpe_ratio": 0.95}}
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief_ok,
        )
        assert needed is False

    def test_evaluate_retraining_need_no_performance_criteria(
        self, mock_retraining_manager, dummy_data
    ):
        mock_retraining_manager.retraining_criteria = {
            "on_performance_degradation": False,
            "min_sharpe_for_retraining": 0.1,
        }
        dummy_brief_degraded = {"overall_performance": {"sharpe_ratio": 0.05}}
        needed = mock_retraining_manager.evaluate_retraining_need(
            dummy_data[0],
            dummy_data[0],
            dummy_data[1],
            dummy_data[1],
            dummy_brief_degraded,
        )
        assert needed is False

    @patch("trading_platform.ai.training.pipeline.AITrainingPipeline")
    def test_trigger_training_pipeline(
        self, MockAITrainingPipeline, mock_retraining_manager
    ):
        mock_retraining_manager.trigger_training_pipeline()
        MockAITrainingPipeline.assert_called_once_with(config_path="config.yaml")
        MockAITrainingPipeline.return_value.run.assert_called_once()
