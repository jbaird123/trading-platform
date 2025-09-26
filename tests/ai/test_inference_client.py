"""
Consolidated tests for trading_platform.ai.inference_client.AIInferenceClient.

Merged behavioural suite with coverage-gap scenarios.
"""

from __future__ import annotations

import logging
from unittest import mock
from unittest.mock import Mock, patch

import httpx
import pandas as pd
import pytest
from trading_platform.ai.inference_client import AIInferenceClient

# --- test_inference_client.py ---


@pytest.fixture
def mock_httpx_client():
    with mock.patch("httpx.Client") as mock_client:
        yield mock_client


@pytest.fixture
def ai_inference_client(mock_httpx_client):
    return AIInferenceClient(base_url="http://test-url")


@pytest.fixture
def mock_send_request(ai_inference_client):
    with mock.patch.object(ai_inference_client, "_send_request") as _mock_send_request:
        yield _mock_send_request


def test_ai_inference_client_init():
    """
    Verifies that AIInferenceClient initializes correctly with default and custom
    parameters.
    """
    client = AIInferenceClient()
    assert client.base_url == "http://localhost:8000"
    assert client.timeout == 5.0
    assert client.retries == 3
    assert client.backoff_factor == 0.5
    assert isinstance(client.client, httpx.Client)

    custom_client = AIInferenceClient(
        base_url="http://custom", timeout=10.0, retries=5, backoff_factor=1.0
    )
    assert custom_client.base_url == "http://custom"
    assert custom_client.timeout == 10.0
    assert custom_client.retries == 5
    assert custom_client.backoff_factor == 1.0


def test_send_request_success(ai_inference_client):
    """
    Tests successful request sending via _send_request.
    """
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    ai_inference_client.client.request.return_value = mock_response

    response = ai_inference_client._send_request("GET", "http://test-url/health")
    assert response == mock_response
    ai_inference_client.client.request.assert_called_once_with(
        "GET", "http://test-url/health"
    )


def test_send_request_retry_mechanism(ai_inference_client):
    """
    Verifies that _send_request retries on httpx.RequestError.
    """
    ai_inference_client.client.request.side_effect = [
        httpx.RequestError("Connection error", request=httpx.Request("GET", "url")),
        httpx.RequestError("Connection error", request=httpx.Request("GET", "url")),
        mock.Mock(spec=httpx.Response, status_code=200, raise_for_status=mock.Mock()),
    ]

    with mock.patch("time.sleep") as mock_sleep:
        response = ai_inference_client._send_request("GET", "http://test-url/health")
        assert response.status_code == 200
        assert ai_inference_client.client.request.call_count == 3
        assert mock_sleep.call_count == 2


def test_send_request_max_retries_exceeded(ai_inference_client):
    """
    Ensures httpx.RequestError is raised when max retries are exceeded.
    """
    ai_inference_client.client.request.side_effect = httpx.RequestError(
        "Connection error", request=httpx.Request("GET", "url")
    )

    with mock.patch("time.sleep"):
        with pytest.raises(httpx.RequestError, match="Max retries exceeded"):
            ai_inference_client._send_request("GET", "http://test-url/health")
        assert (
            ai_inference_client.client.request.call_count == ai_inference_client.retries
        )


def test_send_request_http_status_error(ai_inference_client):
    """
    Confirms httpx.HTTPStatusError is re-raised immediately.
    """
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Client error", request=httpx.Request("GET", "url"), response=mock_response
    )
    ai_inference_client.client.request.return_value = mock_response

    with pytest.raises(httpx.HTTPStatusError, match="Client error"):
        ai_inference_client._send_request("GET", "http://test-url/health")
    ai_inference_client.client.request.assert_called_once()


def test_send_request_other_exception(ai_inference_client):
    """
    Verifies other unexpected exceptions are re-raised immediately.
    """
    ai_inference_client.client.request.side_effect = Exception("Unexpected error")

    with pytest.raises(Exception, match="Unexpected error"):
        ai_inference_client._send_request("GET", "http://test-url/health")
    ai_inference_client.client.request.assert_called_once()


def test_predict_success(ai_inference_client, mock_send_request):
    """
    Tests successful prediction retrieval.
    """
    features = pd.DataFrame({"feature1": [1, 2], "feature2": [3, 4]})
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.json.return_value = [{"prediction": 0.5}, {"prediction": 0.7}]
    mock_send_request.return_value = mock_response

    predictions = ai_inference_client.predict(features)
    assert predictions == [{"prediction": 0.5}, {"prediction": 0.7}]
    mock_send_request.assert_called_once_with(
        "POST", "http://test-url/predict", json=features.to_dict(orient="records")
    )


def test_predict_empty_features(ai_inference_client):
    """
    Ensures an empty list is returned for empty features DataFrame.
    """
    features = pd.DataFrame()
    predictions = ai_inference_client.predict(features)
    assert predictions == []


def test_predict_request_error(ai_inference_client, mock_send_request, caplog):
    """
    Tests error handling when _send_request raises httpx.RequestError during predict.
    """
    mock_send_request.side_effect = httpx.RequestError(
        "Connection error", request=httpx.Request("POST", "url")
    )
    features = pd.DataFrame({"feature1": [1]})

    with caplog.at_level(logging.ERROR):
        predictions = ai_inference_client.predict(features)
        assert predictions == []
        assert "AI inference request failed after retries." in caplog.text


def test_predict_http_status_error(ai_inference_client, mock_send_request, caplog):
    """
    Tests error handling when _send_request raises httpx.HTTPStatusError during predict.
    """
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_send_request.side_effect = httpx.HTTPStatusError(
        "Server error", request=httpx.Request("POST", "url"), response=mock_response
    )
    features = pd.DataFrame({"feature1": [1]})

    with caplog.at_level(logging.ERROR):
        predictions = ai_inference_client.predict(features)
        assert predictions == []
        assert "AI inference HTTP error." in caplog.text


def test_predict_other_exception(ai_inference_client, mock_send_request, caplog):
    """
    Tests error handling when _send_request raises other exceptions during predict.
    """
    mock_send_request.side_effect = Exception("Unexpected predict error")
    features = pd.DataFrame({"feature1": [1]})

    with caplog.at_level(logging.ERROR):
        predictions = ai_inference_client.predict(features)
        assert predictions == []
        assert "An unexpected error occurred during AI inference." in caplog.text


def test_health_check_success(ai_inference_client, mock_send_request):
    """
    Tests successful health check.
    """
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_send_request.return_value = mock_response

    is_healthy = ai_inference_client.health_check()
    assert is_healthy is True
    mock_send_request.assert_called_once_with("GET", "http://test-url/health")


def test_health_check_failure(ai_inference_client, mock_send_request):
    """
    Tests failed health check (non-200 status code).
    """
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_send_request.return_value = mock_response

    is_healthy = ai_inference_client.health_check()
    assert is_healthy is False


def test_health_check_request_error(ai_inference_client, mock_send_request, caplog):
    """
    Tests error handling when _send_request raises httpx.RequestError during
    health check.
    """
    mock_send_request.side_effect = httpx.RequestError(
        "Connection error", request=httpx.Request("GET", "url")
    )

    with caplog.at_level(logging.ERROR):
        is_healthy = ai_inference_client.health_check()
        assert is_healthy is False
        assert "AI inference health check failed after retries." in caplog.text


def test_health_check_http_status_error(ai_inference_client, mock_send_request, caplog):
    """
    Tests error handling when _send_request raises httpx.HTTPStatusError during
    health check.
    """
    mock_response = mock.Mock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_send_request.side_effect = httpx.HTTPStatusError(
        "Server error", request=httpx.Request("GET", "url"), response=mock_response
    )

    with caplog.at_level(logging.ERROR):
        is_healthy = ai_inference_client.health_check()
        assert is_healthy is False
        assert "AI inference health check HTTP error." in caplog.text


def test_health_check_other_exception(ai_inference_client, mock_send_request, caplog):
    """
    Tests error handling when _send_request raises other exceptions during health check.
    """
    mock_send_request.side_effect = Exception("Unexpected health check error")

    with caplog.at_level(logging.ERROR):
        is_healthy = ai_inference_client.health_check()
        assert is_healthy is False
        assert "An unexpected error occurred during AI health check." in caplog.text


# --- test_inference_client_coverage_gaps.py ---

"""
Test coverage gaps in AI Inference Client module.

Targets specific missing lines in ai/inference_client.py to improve coverage.
"""


def test_inference_client_request_error():
    """Test AIInferenceClient when httpx.RequestError is raised. Covers line 67."""

    client = AIInferenceClient("http://test-server:8000")

    # Mock _send_request to raise RequestError
    with patch.object(client, "_send_request") as mock_send:
        mock_send.side_effect = httpx.RequestError("Connection failed", request=None)

        with patch("trading_platform.ai.inference_client.logger") as mock_logger:
            # Create test DataFrame
            test_df = pd.DataFrame([{"feature1": 1.0, "feature2": 2.0}])
            result = client.predict(test_df)

            # Should return empty list on RequestError
            assert result == []

            # Should log the error
            mock_logger.error.assert_called_with(
                "AI inference request failed after " "retries."
            )


def test_inference_client_http_status_error():
    """Test AIInferenceClient when httpx.HTTPStatusError is raised. Covers line 70."""

    client = AIInferenceClient("http://test-server:8000")

    # Mock _send_request to raise HTTPStatusError
    with patch.object(client, "_send_request") as mock_send:
        # Create a mock response for HTTPStatusError
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        # HTTPStatusError requires message, request, and response
        http_error = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )
        mock_send.side_effect = http_error

        with patch("trading_platform.ai.inference_client.logger") as mock_logger:
            # Create test DataFrame
            test_df = pd.DataFrame([{"feature1": 1.0, "feature2": 2.0}])
            result = client.predict(test_df)

            # Should return empty list on HTTPStatusError
            assert result == []

            # Should log the error
            mock_logger.error.assert_called_with("AI inference HTTP error.")


def test_inference_client_non_list_response():
    """Test AIInferenceClient when server returns non-list response. Covers line 64."""

    client = AIInferenceClient("http://test-server:8000")

    # Mock _send_request to return non-list response
    with patch.object(client, "_send_request") as mock_send:
        # Mock response that returns a dict instead of list
        mock_response = Mock()
        mock_response.json.return_value = {"error": "Invalid data format"}
        mock_send.return_value = mock_response

        with patch("trading_platform.ai.inference_client.logger") as mock_logger:
            # Create test DataFrame
            test_df = pd.DataFrame([{"feature1": 1.0, "feature2": 2.0}])
            result = client.predict(test_df)

            # Should return empty list when response is not a list
            assert result == []

            # Should log the error
            mock_logger.error.assert_called_with("Prediction response is not a list.")
