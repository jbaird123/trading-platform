"""
Test coverage gaps in AI Lab Predictor module.

Targets specific missing lines in ai/lab/predictor.py to improve coverage.
"""
import pytest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from trading_platform.ai.lab.predictor import get_trade_insights


def test_get_trade_insights_shap_list_format():
    """Test get_trade_insights when SHAP returns list format. Covers line 25."""
    
    # Create sample data
    features = ["feature1", "feature2", "feature3"]
    trade = {
        "entry_context": {
            "feature1": 1.0,
            "feature2": 2.0,
            "feature3": 3.0
        }
    }
    
    # Mock trained model
    mock_model = Mock()
    mock_model.predict.return_value = [1]  # Predict profitable
    mock_model.predict_proba.return_value = [[0.3, 0.7]]  # 70% probability
    
    # Mock SHAP explainer and values to return list format
    with patch('trading_platform.ai.lab.predictor.shap') as mock_shap:
        mock_explainer = Mock()
        
        # Set up SHAP to return list format (binary classification case)
        # This should trigger line 25: shap_vals = shap_values[1][0]
        mock_explainer.shap_values.return_value = [
            np.array([[0.1, 0.2, 0.3]]),  # Class 0 SHAP values
            np.array([[0.4, 0.5, 0.6]])   # Class 1 SHAP values
        ]
        
        mock_shap.TreeExplainer.return_value = mock_explainer
        
        # Call the function
        result = get_trade_insights(mock_model, trade, features)
        
        # Verify the result structure
        assert isinstance(result, dict)
        assert "predicted_profitable" in result
        assert "predicted_probability" in result
        assert "feature_importances" in result
        
        # Should use Class 1 values (index [1][0]) as per line 25
        expected_values = [0.4, 0.5, 0.6]  # From shap_values[1][0]
        feature_importances = result["feature_importances"]
        for i, feature in enumerate(features):
            assert feature in feature_importances
            assert feature_importances[feature] == expected_values[i]


def test_get_trade_insights_shap_array_format():
    """Test get_trade_insights when SHAP returns array format (else branch)."""
    
    # Create sample data
    features = ["feature1", "feature2"] 
    trade = {
        "entry_context": {
            "feature1": 1.5,
            "feature2": 2.5
        }
    }
    
    # Mock trained model
    mock_model = Mock()
    mock_model.predict.return_value = [0]  # Predict not profitable
    mock_model.predict_proba.return_value = [[0.8, 0.2]]  # 20% probability
    
    # Mock SHAP explainer and values to return array format
    with patch('trading_platform.ai.lab.predictor.shap') as mock_shap:
        mock_explainer = Mock()
        
        # Set up SHAP to return array format (not a list)
        # This should trigger the else branch: shap_vals = shap_values[0]
        mock_explainer.shap_values.return_value = np.array([[0.7, 0.8]])
        
        mock_shap.TreeExplainer.return_value = mock_explainer
        
        # Call the function
        result = get_trade_insights(mock_model, trade, features)
        
        # Verify the result structure
        assert isinstance(result, dict)
        assert "predicted_profitable" in result
        assert "predicted_probability" in result
        assert "feature_importances" in result
        
        # Should use array values directly as per else branch
        expected_values = [0.7, 0.8]  # From shap_values[0]
        feature_importances = result["feature_importances"]
        for i, feature in enumerate(features):
            assert feature in feature_importances
            assert feature_importances[feature] == expected_values[i]