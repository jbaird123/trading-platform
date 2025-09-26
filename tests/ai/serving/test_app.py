import runpy
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from trading_platform.ai.serving.app import (
    API_KEY,
    API_KEY_NAME,
    Feature,
    PredictionRequest,
    app,
)

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
            {"name": "feature2", "value": 2.5},
        ]
    }
    response = client.post(
        "/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] in ["long", "short", "flat"]
    assert isinstance(data["probability"], float)
    assert 0 <= data["probability"] <= 1
    assert data["model_version"] == "v1.0"


def test_predict_unauthorized():
    request_body = {"features": [{"name": "feature1", "value": 1.0}]}
    response = client.post(
        "/v1/predict", json=request_body, headers={API_KEY_NAME: "invalid"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API Key"}


def test_predict_no_api_key():
    request_body = {"features": [{"name": "feature1", "value": 1.0}]}
    response = client.post("/v1/predict", json=request_body)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_predict_invalid_body():
    request_body = {
        "features": [
            {"name": "feature1", "value": "not_a_float"}  # Invalid value type
        ]
    }
    response = client.post(
        "/v1/predict", json=request_body, headers={API_KEY_NAME: API_KEY}
    )
    assert response.status_code == 422  # Unprocessable Entity


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


# --- Consolidated from tests/ai/test_serving_app_coverage_gaps.py ---


def test_predict_signal_branches():
    request_data = {
        "features": [
            {"name": "feature1", "value": 1.0},
            {"name": "feature2", "value": 2.0},
            {"name": "feature3", "value": 3.0},
        ]
    }

    for rand_val, expected_signal in ((0.2, "long"), (0.5, "short"), (0.8, "flat")):
        with patch("numpy.random.rand", return_value=rand_val):
            response = client.post(
                "/v1/predict",
                json=request_data,
                headers={API_KEY_NAME: API_KEY},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["signal"] == expected_signal
        assert payload["probability"] == rand_val


def test_predict_exception_handling():
    request_data = {"features": [{"name": "feature1", "value": 1.0}]}
    with patch("numpy.random.rand", side_effect=Exception("boom")):
        response = client.post(
            "/v1/predict",
            json=request_data,
            headers={API_KEY_NAME: API_KEY},
        )
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


def test_main_block_execution():
    with patch("uvicorn.run") as mock_run:
        sys.modules.pop("trading_platform.ai.serving.app", None)
        runpy.run_module("trading_platform.ai.serving.app", run_name="__main__")

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000


def test_prediction_request_model_validation():
    # Valid request should not raise
    request = PredictionRequest(
        features=[
            Feature(name="feature1", value=1.0),
            Feature(name="feature2", value=2.0),
        ]
    )
    assert len(request.features) == 2

    # Invalid payload should raise a validation error
    with pytest.raises(Exception):
        # Create invalid raw data that will fail pydantic validation
        PredictionRequest.model_validate(
            {"features": [{"name": "feature", "value": "bad"}]}
        )
