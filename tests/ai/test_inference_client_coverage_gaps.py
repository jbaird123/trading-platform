"""
Test coverage gaps in AI Inference Client module.

Targets specific missing lines in ai/inference_client.py to improve coverage.
"""

from unittest.mock import Mock, patch

import httpx
import pandas as pd
from trading_platform.ai.inference_client import AIInferenceClient


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
