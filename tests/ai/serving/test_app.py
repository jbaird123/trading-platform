import pytest
from fastapi.testclient import TestClient
from src.trading_platform.ai.serving.app import app, API_KEY, API_KEY_NAME

client = TestClient(app)

def test_get_api_key_valid():
    response = client.get("/v1/health", headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 200

def test_get_api_key_invalid():
    response = client.get("/v1/health", headers={API_KEY_NAME: "wrong-key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API Key"}

def test_get_api_key_missing():
    response = client.get("/v1/health")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_health_check_success():
    response = client.get("/v1/health", headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "version" in response.json()

def test_health_check_unauthorized():
    response = client.get("/v1/health", headers={API_KEY_NAME: "invalid"})
    assert response.status_code == 401

def test_health_check_no_api_key():
    response = client.get("/v1/health")
    assert response.status_code == 401

def test_predict_success():
    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0},
            {"name": "feature2", "value": 2.5}
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] in ["long", "short", "flat"]
    assert isinstance(data["probability"], float)
    assert 0 <= data["probability"] <= 1
    assert data["model_version"] == "v1.0"

def test_predict_unauthorized():
    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0}
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: "invalid"})
    assert response.status_code == 401

def test_predict_no_api_key():
    request_body = {
        "features": [
            {"name": "feature1", "value": 1.0}
        ]
    }
    response = client.post("/v1/predict", json=request_body)
    assert response.status_code == 401

def test_predict_invalid_body():
    request_body = {
        "features": [
            {"name": "feature1", "value": "not_a_float"} # Invalid value type
        ]
    }
    response = client.post("/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 422 # Unprocessable Entity

def test_metrics_success():
    response = client.get("/v1/metrics", headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "metrics_endpoint_placeholder"
    assert "message" in data
    assert "available_metrics" in data
    assert "version" in data

def test_metrics_unauthorized():
    response = client.get("/v1/metrics", headers={API_KEY_NAME: "invalid"})
    assert response.status_code == 401

def test_metrics_no_api_key():
    response = client.get("/v1/metrics")
    assert response.status_code == 401