import pytest
import logging
import pandas as pd
from src.trading_platform.ai.monitoring.performance_monitor import AIBaseMonitor, AIModelPerformanceMonitor, AIDriftDetector

# --- Tests for AIBaseMonitor ---

def test_aib_init():
    config = {"name": "TestMonitor"}
    monitor = AIBaseMonitor(config)
    assert monitor.config == config
    assert monitor.monitor_name == "TestMonitor"

def test_aib_init_no_name():
    config = {}
    monitor = AIBaseMonitor(config)
    assert monitor.monitor_name == "unnamed_monitor"

def test_aib_check_thresholds_within_range(caplog):
    config = {"name": "TestMonitor", "thresholds": {"metric1": {"min": 10, "max": 20}}}
    monitor = AIBaseMonitor(config)
    with caplog.at_level(logging.WARNING):
        monitor._check_thresholds("metric1", 15)
        assert not caplog.records

def test_aib_check_thresholds_below_min(caplog):
    config = {"name": "TestMonitor", "thresholds": {"metric1": {"min": 10, "max": 20}}}
    monitor = AIBaseMonitor(config)
    with caplog.at_level(logging.WARNING):
        monitor._check_thresholds("metric1", 5)
        assert len(caplog.records) == 1
        assert "below minimum threshold" in caplog.text
        assert "ALERT!" in caplog.text

def test_aib_check_thresholds_above_max(caplog):
    config = {"name": "TestMonitor", "thresholds": {"metric1": {"min": 10, "max": 20}}}
    monitor = AIBaseMonitor(config)
    with caplog.at_level(logging.WARNING):
        monitor._check_thresholds("metric1", 25)
        assert len(caplog.records) == 1
        assert "above maximum threshold" in caplog.text
        assert "ALERT!" in caplog.text

def test_aib_check_thresholds_no_threshold_config(caplog):
    config = {"name": "TestMonitor"}
    monitor = AIBaseMonitor(config)
    with caplog.at_level(logging.WARNING):
        monitor._check_thresholds("metric1", 15)
        assert not caplog.records

def test_aib_check_thresholds_partial_threshold_config(caplog):
    config = {"name": "TestMonitor", "thresholds": {"metric1": {"min": 10}}}
    monitor = AIBaseMonitor(config)
    with caplog.at_level(logging.WARNING):
        monitor._check_thresholds("metric1", 5) # Below min
        assert len(caplog.records) == 1
        assert "below minimum threshold" in caplog.text
        assert "ALERT!" in caplog.text
        caplog.clear()
        monitor._check_thresholds("metric1", 25) # Above max, but no max defined
        assert not caplog.records

def test_aib_trigger_alert(caplog):
    config = {"name": "TestMonitor"}
    monitor = AIBaseMonitor(config)
    with caplog.at_level(logging.ERROR):
        monitor._trigger_alert("test_metric", 123.45, "test_reason")
        assert len(caplog.records) == 1
        assert "ALERT! [TestMonitor] Metric 'test_metric' (123.45) triggered alert due to: test_reason." in caplog.text

# --- Tests for AIModelPerformanceMonitor ---

def test_aimpm_init():
    config = {"name": "PerfMonitor", "metrics": ["sharpe_ratio"]}
    monitor = AIModelPerformanceMonitor(config)
    assert monitor.config == config
    assert monitor.monitor_name == "PerfMonitor"
    assert monitor.metrics_to_monitor == ["sharpe_ratio"]

def test_aimpm_monitor_performance_sharpe_within_threshold(mocker, caplog):
    config = {"name": "PerfMonitor", "metrics": ["sharpe_ratio"], "thresholds": {"sharpe_ratio": {"min": 0.5, "max": 2.0}}}
    monitor = AIModelPerformanceMonitor(config)
    mock_check_thresholds = mocker.patch.object(monitor, '_check_thresholds')
    brief_data = {"overall_performance": {"sharpe_ratio": 1.0}}
    
    with caplog.at_level(logging.INFO):
        monitor.monitor_performance(brief_data)
        assert "Monitoring model performance" in caplog.text
        assert "Current Sharpe Ratio: 1.0" in caplog.text
        mock_check_thresholds.assert_called_once_with("sharpe_ratio", 1.0)

def test_aimpm_monitor_performance_sharpe_below_threshold(mocker, caplog):
    config = {"name": "PerfMonitor", "metrics": ["sharpe_ratio"], "thresholds": {"sharpe_ratio": {"min": 0.5, "max": 2.0}}}
    monitor = AIModelPerformanceMonitor(config)
    mock_check_thresholds = mocker.patch.object(monitor, '_check_thresholds')
    brief_data = {"overall_performance": {"sharpe_ratio": 0.3}}
    
    with caplog.at_level(logging.INFO):
        monitor.monitor_performance(brief_data)
        mock_check_thresholds.assert_called_once_with("sharpe_ratio", 0.3)

def test_aimpm_monitor_performance_no_sharpe_in_brief(mocker, caplog):
    config = {"name": "PerfMonitor", "metrics": ["sharpe_ratio"], "thresholds": {"sharpe_ratio": {"min": 0.5, "max": 2.0}}}
    monitor = AIModelPerformanceMonitor(config)
    mock_check_thresholds = mocker.patch.object(monitor, '_check_thresholds')
    brief_data = {"overall_performance": {}}
    
    with caplog.at_level(logging.INFO):
        monitor.monitor_performance(brief_data)
        assert "Current Sharpe Ratio" not in caplog.text # Should not log if not present
        mock_check_thresholds.assert_not_called()

def test_aimpm_detect_data_drift_no_drift(caplog):
    config = {"name": "PerfMonitor", "drift_detection": {"feature": "price", "threshold": 0.1}}
    monitor = AIModelPerformanceMonitor(config)
    new_data = pd.DataFrame({"price": [10, 11, 12]})
    baseline_data = pd.DataFrame({"price": [10.05, 11.05, 12.05]})
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_data_drift(new_data, baseline_data)
        assert not detected
        assert "Detecting data drift" in caplog.text
        assert "Data drift detected" not in caplog.text

def test_aimpm_detect_data_drift_with_drift(caplog):
    config = {"name": "PerfMonitor", "drift_detection": {"feature": "price", "threshold": 0.01}}
    monitor = AIModelPerformanceMonitor(config)
    new_data = pd.DataFrame({"price": [10, 11, 12]})
    baseline_data = pd.DataFrame({"price": [10.05, 11.05, 12.05]})
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_data_drift(new_data, baseline_data)
        assert detected
        assert "Data drift detected in feature 'price'" in caplog.text
        assert "ALERT!" in caplog.text

def test_aimpm_detect_data_drift_empty_dataframes(caplog):
    config = {"name": "PerfMonitor", "drift_detection": {"feature": "price", "threshold": 0.1}}
    monitor = AIModelPerformanceMonitor(config)
    new_data = pd.DataFrame()
    baseline_data = pd.DataFrame({"price": [1,2,3]})
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_data_drift(new_data, baseline_data)
        assert not detected
        assert "Detecting data drift" in caplog.text
        assert "Data drift detected" not in caplog.text

def test_aimpm_detect_data_drift_feature_not_in_dataframes(caplog):
    config = {"name": "PerfMonitor", "drift_detection": {"feature": "non_existent_feature", "threshold": 0.1}}
    monitor = AIModelPerformanceMonitor(config)
    new_data = pd.DataFrame({"price": [10, 11, 12]})
    baseline_data = pd.DataFrame({"price": [10.05, 11.05, 12.05]})
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_data_drift(new_data, baseline_data)
        assert not detected
        assert "Data drift detected" not in caplog.text

def test_aimpm_detect_concept_drift_no_drift(caplog):
    config = {"name": "PerfMonitor", "concept_drift": {"expected_accuracy": 0.8}}
    monitor = AIModelPerformanceMonitor(config)
    model_predictions = pd.Series([1, 1, 0, 0])
    true_labels = pd.Series([1, 1, 0, 0])
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_concept_drift(model_predictions, true_labels)
        assert not detected
        assert "Detecting concept drift" in caplog.text
        assert "Concept drift detected" not in caplog.text

def test_aimpm_detect_concept_drift_with_drift(caplog):
    config = {"name": "PerfMonitor", "concept_drift": {"expected_accuracy": 0.8}}
    monitor = AIModelPerformanceMonitor(config)
    model_predictions = pd.Series([1, 1, 0, 0])
    true_labels = pd.Series([1, 0, 0, 1]) # Accuracy 0.5
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_concept_drift(model_predictions, true_labels)
        assert detected
        assert "Concept drift detected" in caplog.text
        assert "ALERT!" in caplog.text

def test_aimpm_detect_concept_drift_empty_series(caplog):
    config = {"name": "PerfMonitor", "concept_drift": {"expected_accuracy": 0.8}}
    monitor = AIModelPerformanceMonitor(config)
    model_predictions = pd.Series()
    true_labels = pd.Series([1, 0, 0, 1])
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_concept_drift(model_predictions, true_labels)
        assert not detected
        assert "Detecting concept drift" in caplog.text
        assert "Concept drift detected" not in caplog.text

def test_aimpm_detect_concept_drift_mismatched_lengths(caplog):
    config = {"name": "PerfMonitor", "concept_drift": {"expected_accuracy": 0.8}}
    monitor = AIModelPerformanceMonitor(config)
    model_predictions = pd.Series([1, 1])
    true_labels = pd.Series([1, 0, 0, 1])
    
    with caplog.at_level(logging.INFO):
        detected = monitor.detect_concept_drift(model_predictions, true_labels)
        assert not detected
        assert "Detecting concept drift" in caplog.text
        assert "Concept drift detected" not in caplog.text

# --- Tests for AIDriftDetector ---

def test_aidd_init():
    config = {"name": "DriftDetector"}
    detector = AIDriftDetector(config)
    assert detector.config == config
    assert detector.monitor_name == "DriftDetector"

def test_aidd_detect_data_drift_placeholder():
    config = {}
    detector = AIDriftDetector(config)
    new_data = pd.DataFrame({"a": [1]})
    baseline_data = pd.DataFrame({"a": [2]})
    assert not detector.detect_data_drift(new_data, baseline_data)

def test_aidd_detect_concept_drift_placeholder():
    config = {}
    detector = AIDriftDetector(config)
    model_predictions = pd.Series([1])
    true_labels = pd.Series([0])
    assert not detector.detect_concept_drift(model_predictions, true_labels)

def test_aidd_check_for_drift(mocker):
    config = {"name": "DriftDetector"}
    detector = AIDriftDetector(config)
    
    mock_detect_data_drift = mocker.patch.object(detector, 'detect_data_drift', return_value=True)
    mock_detect_concept_drift = mocker.patch.object(detector, 'detect_concept_drift', return_value=False)
    
    new_data = pd.DataFrame()
    baseline_data = pd.DataFrame()
    model_predictions = pd.Series()
    true_labels = pd.Series()
    
    result = detector.check_for_drift(new_data, baseline_data, model_predictions, true_labels)
    
    mock_detect_data_drift.assert_called_once_with(new_data, baseline_data)
    mock_detect_concept_drift.assert_called_once_with(model_predictions, true_labels)
    assert result == {"data_drift_detected": True, "concept_drift_detected": False}