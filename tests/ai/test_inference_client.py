from unittest.mock import MagicMock, patch

import httpx
import pytest

from trading_platform.ai.inference_client import AIInferenceClient


@pytest.fixture
def mock_httpx_client():
    """Fixture to mock httpx.Client and its post method."""
    with patch("httpx.Client") as mock_client_class:
        mock_client_instance = mock_client_class.return_value
        yield mock_client_instance


def test_ai_inference_client_predict_success(mock_httpx_client):
    """
    Tests that the predict method correctly sends a request and returns a prediction.
    """
    # Arrange
    mock_httpx_client.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"prediction": 0.75, "confidence": 0.9},
        raise_for_status=lambda: None,
    )
    client = AIInferenceClient(base_url="http://test-url:8000")
    features = [1.0, 2.0, 3.0]

    # Act
    result = client.predict(features)

    # Assert
    mock_httpx_client.post.assert_called_once_with(
        "http://test-url:8000/predict", json={"features": features}
    )
    assert result == {"prediction": 0.75, "confidence": 0.9}


def test_ai_inference_client_predict_http_error(mock_httpx_client):
    """
    Tests that the predict method raises an HTTPStatusError on non-2xx responses.
    """
    # Arrange
    mock_response = MagicMock(
        status_code=404,
        json=lambda: {"detail": "Not Found"},
    )
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=httpx.Request("POST", "http://test-url:8000/predict"), response=httpx.Response(404)
    )
    mock_httpx_client.post.return_value = mock_response

    client = AIInferenceClient(base_url="http://test-url:8000")
    features = [1.0, 2.0, 3.0]

    # Act & Assert
    with pytest.raises(httpx.HTTPStatusError):
        client.predict(features)


def test_ai_inference_client_predict_invalid_features():
    """
    Tests that the predict method raises ValueError for invalid features input.
    """
    client = AIInferenceClient()
    with pytest.raises(ValueError, match="Features must be a list of numbers."):
        client.predict([1, "invalid", 3])
    with pytest.raises(ValueError, match="Features must be a list of numbers."):
        client.predict("not a list")


def test_ai_inference_client_client_close():
    """
    Tests that the httpx client is closed when AIInferenceClient is deleted.
    """
    with patch("httpx.Client") as mock_client_class:
        mock_client_instance = mock_client_class.return_value
        client = AIInferenceClient()
        del client
        mock_client_instance.close.assert_called_once()
