import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.trading_platform.ai.serving.app import app, API_KEY, API_KEY_NAME

client = TestClient(app)

@patch("src.trading_platform.ai.serving.app.np.random.rand")
def test_predict_integration_success(mock_np_random_rand):
    # Mock the random prediction to be deterministic for testing
    mock_np_random_rand.return_value = 0.1 # Will result in 'long'

    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0},
            {"name": "feature2", "value": 2.5}
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY})
    
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "long"
    assert isinstance(data["probability"], float)
    assert data["model_version"] == "v1.0"

    # Verify that the random function was called (simulating internal logic)
    mock_np_random_rand.assert_called_once()

@patch("src.trading_platform.ai.serving.app.np.random.rand")
def test_predict_integration_internal_error(mock_np_random_rand):
    # Simulate an internal error during prediction
    mock_np_random_rand.side_effect = Exception("Simulated internal error")

    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0}
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY})
    
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error during prediction."}

@patch("src.trading_platform.ai.serving.app.API_KEY", "wrong-key")
def test_predict_integration_unauthorized_api_key():
    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0}
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: "invalid-key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API Key"}

def test_predict_integration_missing_api_key():
    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0}
        ]
    }
    response = client.post("/v1/predict", json=request_body)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_predict_integration_invalid_request_body():
    request_body = {
        "features": [
            {"name": "feature1", "value": "not_a_float"} # Invalid value type
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 422 # Unprocessable Entity
