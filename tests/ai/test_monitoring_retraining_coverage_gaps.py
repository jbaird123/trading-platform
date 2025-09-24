"""
Test coverage gaps for AI monitoring retraining_manager module.
Targets specific lines that need coverage to reach 100%.
"""
import pytest
from unittest.mock import Mock, patch
import os
import sys


def test_performance_degradation_retraining():
    """Test retraining trigger due to performance degradation - targets lines 64->74."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    # Create retraining manager with degradation criteria
    config = {
        "retraining_criteria": {
            "on_performance_degradation": True,  # Enable performance check
            "min_sharpe_for_retraining": 1.0,  # Set threshold
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Mock performance brief with low sharpe ratio to trigger retraining
    current_performance_brief = {
        "overall_performance": {
            "sharpe_ratio": 0.5  # Below threshold of 1.0
        }
    }
    
    # Create dummy data for the method parameters
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    
    # Mock the drift detector to avoid drift triggers
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": False,
        "concept_drift_detected": False
    }):
        # This should trigger the retraining due to poor performance (lines 64-74)
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Verify retraining is triggered
        assert result is True


def test_performance_above_threshold():
    """Test that retraining is not triggered when performance is good."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    # Create retraining manager with degradation criteria
    config = {
        "retraining_criteria": {
            "on_performance_degradation": True,  # Enable performance check
            "min_sharpe_for_retraining": 1.0,  # Set threshold
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Mock performance brief with good sharpe ratio
    current_performance_brief = {
        "overall_performance": {
            "sharpe_ratio": 1.5  # Above threshold of 1.0
        }
    }
    
    # Create dummy data for the method parameters
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    
    # Mock the drift detector to avoid drift triggers
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": False,
        "concept_drift_detected": False
    }):
        # This should NOT trigger retraining due to good performance
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Verify retraining is not triggered
        assert result is False


def test_scheduled_retraining_check():
    """Test scheduled retraining check - targets lines 78-79."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    # Create retraining manager with scheduled interval to trigger the branch
    config = {
        "retraining_criteria": {
            "scheduled_interval": "weekly",  # Set to trigger scheduled check
            "on_performance_degradation": False,  # No performance check
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Mock performance brief with no sharpe data to avoid performance trigger
    current_performance_brief = {
        "overall_performance": {}  # No sharpe_ratio data
    }
    
    # Create dummy data for the method parameters
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    
    # Mock the drift detector to avoid drift triggers
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": False,
        "concept_drift_detected": False
    }):
        # This should exercise the scheduled retraining check (lines 78-79)
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Currently returns False as it's a placeholder, but exercises the code
        assert result is False


def test_missing_performance_data():
    """Test handling when performance data is missing."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    config = {
        "retraining_criteria": {
            "on_performance_degradation": True,
            "min_sharpe_for_retraining": 1.0,
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Mock performance brief with missing overall_performance data
    current_performance_brief = {}  # Missing overall_performance key
    
    # Create dummy data
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    
    # Mock the drift detector to avoid drift triggers
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": False,
        "concept_drift_detected": False
    }):
        # This should not trigger retraining due to missing data
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Verify retraining is not triggered
        assert result is False


def test_none_sharpe_values():
    """Test handling when sharpe values are None."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    config = {
        "retraining_criteria": {
            "on_performance_degradation": True,
            "min_sharpe_for_retraining": None,  # None threshold
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Mock performance brief with None sharpe
    current_performance_brief = {
        "overall_performance": {
            "sharpe_ratio": None
        }
    }
    
    # Create dummy data
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    
    # Mock the drift detector to avoid drift triggers
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": False,
        "concept_drift_detected": False
    }):
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Should not trigger due to None values
        assert result is False


def test_data_drift_trigger():
    """Test retraining trigger due to data drift - targets lines 47-48."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    config = {
        "retraining_criteria": {
            "on_data_drift": True,  # Enable data drift trigger
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Create dummy data
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    current_performance_brief = {}
    
    # Mock the drift detector to return data drift detected
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": True,  # Trigger data drift
        "concept_drift_detected": False
    }):
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Should trigger retraining due to data drift
        assert result is True


def test_concept_drift_trigger():
    """Test retraining trigger due to concept drift - targets lines 51-52."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    import pandas as pd
    
    config = {
        "retraining_criteria": {
            "on_concept_drift": True,  # Enable concept drift trigger
        }
    }
    
    manager = AIRetrainingManager(config)
    
    # Create dummy data
    new_data = pd.DataFrame({"feature1": [1, 2, 3]})
    baseline_data = pd.DataFrame({"feature1": [1, 2, 3]})
    model_predictions = pd.Series([1, 0, 1])
    true_labels = pd.Series([1, 0, 1])
    current_performance_brief = {}
    
    # Mock the drift detector to return concept drift detected
    with patch.object(manager.drift_detector, 'check_for_drift', return_value={
        "data_drift_detected": False,
        "concept_drift_detected": True  # Trigger concept drift
    }):
        result = manager.evaluate_retraining_need(
            new_data, baseline_data, model_predictions, true_labels, current_performance_brief
        )
        
        # Should trigger retraining due to concept drift
        assert result is True


def test_trigger_training_pipeline():
    """Test the trigger_training_pipeline method - targets lines 86-92."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.monitoring.retraining_manager import AIRetrainingManager
    from unittest.mock import Mock
    
    config = {"retraining_criteria": {}}
    manager = AIRetrainingManager(config)
    
    # Create a mock module for the AITrainingPipeline
    mock_pipeline_module = Mock()
    mock_pipeline_class = Mock()
    mock_pipeline_instance = Mock()
    
    mock_pipeline_class.return_value = mock_pipeline_instance
    mock_pipeline_module.AITrainingPipeline = mock_pipeline_class
    
    # Inject the mock module into sys.modules before the import
    sys.modules['trading_platform.ai.training.pipeline'] = mock_pipeline_module
    
    try:
        # Call the method - this should now successfully run lines 91-92
        manager.trigger_training_pipeline()
        
        # Verify the pipeline was created and run
        mock_pipeline_class.assert_called_once_with(config_path="config.yaml")
        mock_pipeline_instance.run.assert_called_once()
        
    finally:
        # Clean up the mock module
        if 'trading_platform.ai.training.pipeline' in sys.modules:
            del sys.modules['trading_platform.ai.training.pipeline']