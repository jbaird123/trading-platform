import logging
from unittest import mock

import pandas as pd
import pytest

from src.trading_platform.ai.monitoring.performance_monitor import (
    AIDriftDetector,
    AIModelPerformanceMonitor,
)
from src.trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager


@pytest.fixture
def retraining_manager_config():
    return {
        "retraining_criteria": {
            "on_data_drift": True,
            "on_concept_drift": True,
            "on_performance_degradation": True,
            "min_sharpe_for_retraining": 0.5,
            "scheduled_interval": "monthly",
        },
        "drift_detector_config": {"name": "TestDriftDetector"},
        "performance_monitor_config": {"name": "TestPerfMonitor"},
    }


@pytest.fixture
def mock_drift_detector():
    with mock.patch("src.trading_platform.ai.monitoring.retraining_manager.AIDriftDetector") as MockClass:
        instance = MockClass.return_value
        instance.check_for_drift.return_value = {
            "data_drift_detected": False,
            "concept_drift_detected": False,
        }
        yield instance


@pytest.fixture
def mock_performance_monitor():
    with mock.patch(
        "src.trading_platform.ai.monitoring.retraining_manager.AIModelPerformanceMonitor"
    ) as MockClass:
        instance = MockClass.return_value
        yield instance


class TestAIRetrainingManager:
    def test_init(self, retraining_manager_config, mock_drift_detector, mock_performance_monitor):
        manager = AIRetrainingManager(retraining_manager_config)
        assert manager.config == retraining_manager_config
        assert manager.retraining_criteria == retraining_manager_config["retraining_criteria"]
        assert manager.drift_detector == mock_drift_detector
        assert manager.performance_monitor == mock_performance_monitor
        mock_drift_detector.check_for_drift.assert_not_called()  # Ensure not called during init

    def test_evaluate_retraining_need_data_drift_triggers(
        self,
        retraining_manager_config,
        mock_drift_detector,
        mock_performance_monitor,
        caplog,
    ):
        mock_drift_detector.check_for_drift.return_value = {
            "data_drift_detected": True,
            "concept_drift_detected": False,
        }
        manager = AIRetrainingManager(retraining_manager_config)
        with caplog.at_level(logging.WARNING):
            needs_retraining = manager.evaluate_retraining_need(
                pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series(), {}
            )
            assert needs_retraining is True
            assert "Retraining triggered: Data drift detected." in caplog.text

    def test_evaluate_retraining_need_concept_drift_triggers(
        self,
        retraining_manager_config,
        mock_drift_detector,
        mock_performance_monitor,
        caplog,
    ):
        mock_drift_detector.check_for_drift.return_value = {
            "data_drift_detected": False,
            "concept_drift_detected": True,
        }
        manager = AIRetrainingManager(retraining_manager_config)
        with caplog.at_level(logging.WARNING):
            needs_retraining = manager.evaluate_retraining_need(
                pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series(), {}
            )
            assert needs_retraining is True
            assert "Retraining triggered: Concept drift detected." in caplog.text

    def test_evaluate_retraining_need_performance_degradation_triggers(
        self,
        retraining_manager_config,
        mock_drift_detector,
        mock_performance_monitor,
        caplog,
    ):
        current_brief = {"overall_performance": {"sharpe_ratio": 0.4}}
        manager = AIRetrainingManager(retraining_manager_config)
        with caplog.at_level(logging.WARNING):
            needs_retraining = manager.evaluate_retraining_need(
                pd.DataFrame(),
                pd.DataFrame(),
                pd.Series(),
                pd.Series(),
                current_brief,
            )
            assert needs_retraining is True
            assert "Retraining triggered: Performance degradation detected." in caplog.text

    def test_evaluate_retraining_need_no_retraining(
        self,
        retraining_manager_config,
        mock_drift_detector,
        mock_performance_monitor,
        caplog,
    ):
        current_brief = {"overall_performance": {"sharpe_ratio": 0.6}}
        manager = AIRetrainingManager(retraining_manager_config)
        with caplog.at_level(logging.INFO):
            needs_retraining = manager.evaluate_retraining_need(
                pd.DataFrame(),
                pd.DataFrame(),
                pd.Series(),
                pd.Series(),
                current_brief,
            )
            assert needs_retraining is False
            assert "No retraining needed at this time." in caplog.text

    def test_evaluate_retraining_need_missing_criteria_in_config(
        self,
        mock_drift_detector,
        mock_performance_monitor,
        caplog,
    ):
        config = {
            "retraining_criteria": {
                "on_data_drift": False,
                "on_concept_drift": False,
                "on_performance_degradation": False,
            }
        }
        manager = AIRetrainingManager(config)
        with caplog.at_level(logging.INFO):
            needs_retraining = manager.evaluate_retraining_need(
                pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series(), {}
            )
            assert needs_retraining is False

    def test_evaluate_retraining_need_scheduled_retraining_placeholder(
        self,
        retraining_manager_config,
        mock_drift_detector,
        mock_performance_monitor,
        caplog,
    ):
        # Disable other triggers to isolate scheduled check
        retraining_manager_config["retraining_criteria"]["on_data_drift"] = False
        retraining_manager_config["retraining_criteria"]["on_concept_drift"] = False
        retraining_manager_config["retraining_criteria"]["on_performance_degradation"] = False

        manager = AIRetrainingManager(retraining_manager_config)
        with caplog.at_level(logging.INFO):
            needs_retraining = manager.evaluate_retraining_need(
                pd.DataFrame(), pd.DataFrame(), pd.Series(), pd.Series(), {}
            )
            assert "Scheduled retraining check (placeholder)." in caplog.text
            # Since it's a placeholder, it will still return False unless explicitly set
            assert needs_retraining is False

    def test_trigger_training_pipeline(self, retraining_manager_config, caplog):
        manager = AIRetrainingManager(retraining_manager_config)
        with caplog.at_level(logging.INFO):
            manager.trigger_training_pipeline()
            assert "Initiating AI model training pipeline (placeholder)..." in caplog.text
