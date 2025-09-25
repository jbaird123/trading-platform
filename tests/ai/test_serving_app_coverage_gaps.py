"""
Test coverage gaps for AI serving app module.
Targets specific lines that need coverage to reach 100%.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import subprocess


class TestServingAppCoverage:
    """Test class for serving app coverage gaps."""
    
    def setup_method(self):
        """Setup test client for each test."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
        
        from trading_platform.ai.serving.app import app
        from fastapi.testclient import TestClient
        
        self.client = TestClient(app)

    def test_predict_endpoint_signal_branches(self):
        """Test all signal generation branches in predict endpoint - targets lines 108-111."""
        # Add API key header for authentication
        headers = {"X-API-Key": "your-super-secret-api-key"}
        
        # Create proper request payload
        request_data = {
            "features": [
                {"name": "feature1", "value": 1.0},
                {"name": "feature2", "value": 2.0},
                {"name": "feature3", "value": 3.0}
            ]
        }
        
        # Test "long" signal (rand_val < 0.33)
        with patch('numpy.random.rand', return_value=0.2):  # < 0.33
            response = self.client.post("/v1/predict", json=request_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["signal"] == "long"
            assert data["probability"] == 0.2
        
        # Test "short" signal (0.33 <= rand_val < 0.66) 
        with patch('numpy.random.rand', return_value=0.5):  # Between 0.33 and 0.66
            response = self.client.post("/v1/predict", json=request_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["signal"] == "short"
            assert data["probability"] == 0.5
        
        # Test "flat" signal (rand_val >= 0.66)
        with patch('numpy.random.rand', return_value=0.8):  # >= 0.66
            response = self.client.post("/v1/predict", json=request_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["signal"] == "flat"
            assert data["probability"] == 0.8

    def test_predict_endpoint_exception_handling(self):
        """Test exception handling in predict endpoint."""
        headers = {"X-API-Key": "your-super-secret-api-key"}
        
        # Create proper request payload
        request_data = {
            "features": [
                {"name": "feature1", "value": 1.0},
                {"name": "feature2", "value": 2.0}
            ]
        }
        
        # Force an exception by patching numpy.random.rand to raise an error
        with patch('numpy.random.rand', side_effect=Exception("Test error")):
            response = self.client.post("/v1/predict", json=request_data, headers=headers)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Internal server error" in data["detail"]

    def test_health_endpoint(self):
        """Test the health endpoint (covers lines 133-134)."""
        headers = {"X-API-Key": "your-super-secret-api-key"}
        response = self.client.get("/v1/health", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "1.0.0"}

    def test_predict_endpoint_missing_api_key(self):
        """Test predict endpoint without API key (covers lines 42-43)."""
        # Test missing API key
        response = self.client.post("/v1/predict", json={"features": [1.0, 2.0, 3.0]})
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    def test_predict_endpoint_invalid_api_key(self):
        """Test predict endpoint with invalid API key (covers lines 52-53)."""
        # Test invalid API key
        headers = {"X-API-Key": "invalid-key"}
        response = self.client.post("/v1/predict", headers=headers, json={"features": [1.0, 2.0, 3.0]})
        assert response.status_code == 401
        assert "Invalid API Key" in response.json()["detail"]

    def test_metrics_endpoint(self):
        """Test the metrics endpoint (covers lines 143-144)."""
        headers = {"X-API-Key": "your-super-secret-api-key"}
        response = self.client.get("/v1/metrics", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "metrics_endpoint_placeholder"
        assert data["version"] == "1.0.0"
        assert "available_metrics" in data


def test_main_block_execution():
    """Test the main block execution (covers lines 153-155)."""
    from unittest.mock import patch, MagicMock
    import sys
    import importlib.util
    
    # Mock uvicorn to avoid starting server
    mock_uvicorn = MagicMock()
    with patch.dict('sys.modules', {'uvicorn': mock_uvicorn}):
        # Load the module and execute it as __main__
        spec = importlib.util.spec_from_file_location("__main__", 
            "/Users/jbaird/Documents/personal/trading-platform/src/trading_platform/ai/serving/app.py")
        assert spec is not None, "Failed to create module spec"
        module = importlib.util.module_from_spec(spec)
        
        # Execute the module which will trigger the main block
        assert spec.loader is not None, "Loader is None"
        spec.loader.exec_module(module)
        
        # Verify uvicorn.run was called
        mock_uvicorn.run.assert_called_once()
        args, kwargs = mock_uvicorn.run.call_args
        assert kwargs["host"] == "0.0.0.0" 
        assert kwargs["port"] == 8000


def test_prediction_request_model():
    """Test the PredictionRequest model validation."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))
    
    from trading_platform.ai.serving.app import PredictionRequest, Feature
    
    # Valid request
    features = [
        Feature(name="feature1", value=1.0),
        Feature(name="feature2", value=2.0)
    ]
    request = PredictionRequest(features=features)
    assert len(request.features) == 2
    assert request.features[0].name == "feature1"
    assert request.features[0].value == 1.0