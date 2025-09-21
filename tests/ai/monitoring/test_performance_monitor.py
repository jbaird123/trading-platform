import logging
from unittest import mock

import pandas as pd
import pytest

from src.trading_platform.ai.monitoring.performance_monitor import (
    AIBaseMonitor,
    AIModelPerformanceMonitor,
    AIDriftDetector,
)


@pytest.fixture
def base_monitor_config():
    return {"name": "TestMonitor", "thresholds": {"metric_a": {"min": 0.1, "max": 0.9}}}


@pytest.fixture
def performance_monitor_config():
    return {
        "name": "PerfMonitor",
        "metrics": ["sharpe_ratio"],
        "thresholds": {"sharpe_ratio": {"min": 0.5}},
        "drift_detection": {"feature": "feature_x", "threshold": 0.05},
        "concept_drift": {"expected_accuracy": 0.7},
    }


@pytest.fixture
def brief_data_with_sharpe():
    return {"overall_performance": {"sharpe_ratio": 0.6}}


@pytest.fixture
def brief_data_without_sharpe():
    return {"overall_performance": {"accuracy": 0.8}}


@pytest.fixture
def sample_data_drift():
    new_data = pd.DataFrame({"feature_x": [0.6, 0.65, 0.7]})
    baseline_data = pd.DataFrame({"feature_x": [0.5, 0.52, 0.53]})
    return new_data, baseline_data


@pytest.fixture
def sample_data_no_drift():
    new_data = pd.DataFrame({"feature_x": [0.51, 0.52, 0.53]})
    baseline_data = pd.DataFrame({"feature_x": [0.5, 0.52, 0.53]})
    return new_data, baseline_data


@pytest.fixture
def sample_concept_drift():
    model_predictions = pd.Series([1, 0, 1, 0, 1])
    true_labels = pd.Series([1, 1, 0, 0, 0])  # Accuracy = 2/5 = 0.4
    return model_predictions, true_labels


@pytest.fixture
def sample_concept_no_drift():
    model_predictions = pd.Series([1, 1, 1, 0, 0])
    true_labels = pd.Series([1, 1, 1, 0, 0])  # Accuracy = 1.0
    return model_predictions, true_labels


class TestAIBaseMonitor:
    def test_init(self, base_monitor_config):
        monitor = AIBaseMonitor(base_monitor_config)
        assert monitor.config == base_monitor_config
        assert monitor.monitor_name == "TestMonitor"

    @mock.patch.object(AIBaseMonitor, "_trigger_alert")
    def test_check_thresholds_below_min(self, mock_trigger_alert, base_monitor_config, caplog):
        monitor = AIBaseMonitor(base_monitor_config)
        with caplog.at_level(logging.WARNING):
            monitor._check_thresholds("metric_a", 0.05)
            mock_trigger_alert.assert_called_once_with("metric_a", 0.05, "below_min")
            assert "below minimum threshold" in caplog.text

    @mock.patch.object(AIBaseMonitor, "_trigger_alert")
    def test_check_thresholds_above_max(self, mock_trigger_alert, base_monitor_config, caplog):
        monitor = AIBaseMonitor(base_monitor_config)
        with caplog.at_level(logging.WARNING):
            monitor._check_thresholds("metric_a", 0.95)
            mock_trigger_alert.assert_called_once_with("metric_a", 0.95, "above_max")
            assert "above maximum threshold" in caplog.text

    @mock.patch.object(AIBaseMonitor, "_trigger_alert")
    def test_check_thresholds_within_range(self, mock_trigger_alert, base_monitor_config, caplog):
        monitor = AIBaseMonitor(base_monitor_config)
        with caplog.at_level(logging.WARNING):
            monitor._check_thresholds("metric_a", 0.5)
            mock_trigger_alert.assert_not_called()
            assert "" == caplog.text  # No warning should be logged

    @mock.patch.object(AIBaseMonitor, "_trigger_alert")
    def test_check_thresholds_no_threshold_defined(self, mock_trigger_alert, base_monitor_config):
        monitor = AIBaseMonitor(base_monitor_config)
        monitor._check_thresholds("metric_b", 0.5)
        mock_trigger_alert.assert_not_called()

    def test_trigger_alert(self, base_monitor_config, caplog):
        monitor = AIBaseMonitor(base_monitor_config)
        with caplog.at_level(logging.ERROR):
            monitor._trigger_alert("test_metric", 1.23, "test_reason")
            assert "ALERT! [TestMonitor] Metric 'test_metric' (1.23) triggered alert due to: test_reason." in caplog.text


class TestAIModelPerformanceMonitor:
    def test_init(self, performance_monitor_config):
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        assert monitor.config == performance_monitor_config
        assert monitor.monitor_name == "PerfMonitor"
        assert monitor.metrics_to_monitor == ["sharpe_ratio"]

    @mock.patch.object(AIModelPerformanceMonitor, "_check_thresholds")
    def test_monitor_performance_with_sharpe(self, mock_check_thresholds, performance_monitor_config, brief_data_with_sharpe, caplog):
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.INFO):
            monitor.monitor_performance(brief_data_with_sharpe)
            mock_check_thresholds.assert_called_once_with("sharpe_ratio", 0.6)
            assert "Current Sharpe Ratio: 0.6" in caplog.text

    @mock.patch.object(AIModelPerformanceMonitor, "_check_thresholds")
    def test_monitor_performance_without_sharpe(self, mock_check_thresholds, performance_monitor_config, brief_data_without_sharpe, caplog):
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.INFO):
            monitor.monitor_performance(brief_data_without_sharpe)
            mock_check_thresholds.assert_not_called()
            assert "Current Sharpe Ratio" not in caplog.text

    @mock.patch.object(AIModelPerformanceMonitor, "_trigger_alert")
    def test_detect_data_drift_triggered(self, mock_trigger_alert, performance_monitor_config, sample_data_drift, caplog):
        new_data, baseline_data = sample_data_drift
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.WARNING):
            drift_detected = monitor.detect_data_drift(new_data, baseline_data)
            assert drift_detected is True
            mock_trigger_alert.assert_called_once()
            assert "Data drift detected in feature 'feature_x'" in caplog.text

    @mock.patch.object(AIModelPerformanceMonitor, "_trigger_alert")
    def test_detect_data_drift_not_triggered(self, mock_trigger_alert, performance_monitor_config, sample_data_no_drift, caplog):
        new_data, baseline_data = sample_data_no_drift
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.INFO):
            drift_detected = monitor.detect_data_drift(new_data, baseline_data)
            assert drift_detected is False
            mock_trigger_alert.assert_not_called()
            assert "Data drift detected" not in caplog.text

    @mock.patch.object(AIModelPerformanceMonitor, "_trigger_alert")
    def test_detect_data_drift_empty_data(self, mock_trigger_alert, performance_monitor_config, caplog):
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.INFO):
            drift_detected = monitor.detect_data_drift(pd.DataFrame(), pd.DataFrame())
            assert drift_detected is False
            mock_trigger_alert.assert_not_called()

    @mock.patch.object(AIModelPerformanceMonitor, "_trigger_alert")
    def test_detect_concept_drift_triggered(self, mock_trigger_alert, performance_monitor_config, sample_concept_drift, caplog):
        model_predictions, true_labels = sample_concept_drift
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.WARNING):
            drift_detected = monitor.detect_concept_drift(model_predictions, true_labels)
            assert drift_detected is True
            mock_trigger_alert.assert_called_once()
            assert "Concept drift detected" in caplog.text

    @mock.patch.object(AIModelPerformanceMonitor, "_trigger_alert")
    def test_detect_concept_drift_not_triggered(self, mock_trigger_alert, performance_monitor_config, sample_concept_no_drift, caplog):
        model_predictions, true_labels = sample_concept_no_drift
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.INFO):
            drift_detected = monitor.detect_concept_drift(model_predictions, true_labels)
            assert drift_detected is False
            mock_trigger_alert.assert_not_called()
            assert "Concept drift detected" not in caplog.text

    @mock.patch.object(AIModelPerformanceMonitor, "_trigger_alert")
    def test_detect_concept_drift_empty_or_mismatched_data(self, mock_trigger_alert, performance_monitor_config, caplog):
        monitor = AIModelPerformanceMonitor(performance_monitor_config)
        with caplog.at_level(logging.INFO):
            drift_detected = monitor.detect_concept_drift(pd.Series(), pd.Series())
            assert drift_detected is False
            mock_trigger_alert.assert_not_called()

            drift_detected = monitor.detect_concept_drift(pd.Series([1]), pd.Series([1, 0]))
            assert drift_detected is False
            mock_trigger_alert.assert_not_called()


class TestAIDriftDetector:
    def test_init(self, performance_monitor_config):
        detector = AIDriftDetector(performance_monitor_config)
        assert detector.config == performance_monitor_config
        assert detector.monitor_name == "PerfMonitor"

    @mock.patch.object(AIDriftDetector, "detect_concept_drift", return_value=True)
    @mock.patch.object(AIDriftDetector, "detect_data_drift", return_value=True)
    def test_check_for_drift_all_detected(self, mock_data_drift, mock_concept_drift, performance_monitor_config):
        detector = AIDriftDetector(performance_monitor_config)
        new_data = pd.DataFrame()
        baseline_data = pd.DataFrame()
        model_predictions = pd.Series()
        true_labels = pd.Series()

        results = detector.check_for_drift(new_data, baseline_data, model_predictions, true_labels)

        mock_data_drift.assert_called_once_with(new_data, baseline_data)
        mock_concept_drift.assert_called_once_with(model_predictions, true_labels)
        assert results == {"data_drift_detected": True, "concept_drift_detected": True}

    @mock.patch.object(AIDriftDetector, "detect_concept_drift", return_value=False)
    @mock.patch.object(AIDriftDetector, "detect_data_drift", return_value=False)
    def test_check_for_drift_none_detected(self, mock_data_drift, mock_concept_drift, performance_monitor_config):
        detector = AIDriftDetector(performance_monitor_config)
        new_data = pd.DataFrame()
        baseline_data = pd.DataFrame()
        model_predictions = pd.Series()
        true_labels = pd.Series()

        results = detector.check_for_drift(new_data, baseline_data, model_predictions, true_labels)

        assert results == {"data_drift_detected": False, "concept_drift_detected": False}
