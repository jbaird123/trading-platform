from unittest.mock import Mock, patch

import pytest
from trading_platform.ai.llm_analysis.client import LlmApiClient

pytestmark = pytest.mark.skip(reason="LLM client tests await Gemini API implementation")


def test_llm_api_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable not set"):
        LlmApiClient()


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_llm_api_client_initialization_with_api_key(
    mock_model_class, mock_configure, monkeypatch
):
    """Test successful initialization with API key - covers lines 13-14."""
    # Set up environment
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    # Create mock model instance
    mock_model = Mock()
    mock_model_class.return_value = mock_model

    # Initialize client
    client = LlmApiClient()

    # Verify genai.configure was called with the API key
    mock_configure.assert_called_once_with(api_key="test-api-key")

    # Verify GenerativeModel was created with correct model name
    mock_model_class.assert_called_once_with("gemini-2.5-flash")

    # Verify the model is stored
    assert client._model is mock_model


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_get_feedback_success(mock_model_class, mock_configure, monkeypatch):
    """Test successful get_feedback call - covers lines 18-26 success path."""
    # Set up environment and mocks
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_response = Mock()
    mock_response.text = "This is the LLM response text"

    mock_model = Mock()
    mock_model.generate_content.return_value = mock_response
    mock_model_class.return_value = mock_model

    # Initialize client and call get_feedback
    client = LlmApiClient()
    result = client.get_feedback("test prompt")

    # Verify the model was called with the prompt
    mock_model.generate_content.assert_called_once_with("test prompt")

    # Verify the response text was returned
    assert result == "This is the LLM response text"


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_get_feedback_no_text_attribute(mock_model_class, mock_configure, monkeypatch):
    """Test get_feedback when response has no text attribute - covers lines 21-23."""
    # Set up environment and mocks
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_response = Mock()
    # Don't set text attribute to simulate missing text
    del mock_response.text

    mock_model = Mock()
    mock_model.generate_content.return_value = mock_response
    mock_model_class.return_value = mock_model

    # Initialize client and call get_feedback
    client = LlmApiClient()
    result = client.get_feedback("test prompt")

    # Should return error message when text is None
    assert result == "Error: LLM response did not contain text."


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_get_feedback_non_string_text(mock_model_class, mock_configure, monkeypatch):
    """Test get_feedback when response text is not a string - covers lines 21-23."""
    # Set up environment and mocks
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_response = Mock()
    mock_response.text = 123  # Non-string text

    mock_model = Mock()
    mock_model.generate_content.return_value = mock_response
    mock_model_class.return_value = mock_model

    # Initialize client and call get_feedback
    client = LlmApiClient()
    result = client.get_feedback("test prompt")

    # Should return error message when text is not a string
    assert result == "Error: LLM response did not contain text."


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_get_feedback_api_exception(mock_model_class, mock_configure, monkeypatch):
    """Test get_feedback when API call raises an exception - covers lines 25-26."""
    # Set up environment and mocks
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_model = Mock()
    mock_model.generate_content.side_effect = Exception("API connection failed")
    mock_model_class.return_value = mock_model

    # Initialize client and call get_feedback
    client = LlmApiClient()
    result = client.get_feedback("test prompt")

    # Should return error message with exception details
    assert result == "Error generating LLM feedback: API connection failed"


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_get_feedback_timeout_exception(mock_model_class, mock_configure, monkeypatch):
    """Test get_feedback with timeout exception - covers exception handling."""
    # Set up environment and mocks
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    mock_model = Mock()
    mock_model.generate_content.side_effect = TimeoutError("Request timed out")
    mock_model_class.return_value = mock_model

    # Initialize client and call get_feedback
    client = LlmApiClient()
    result = client.get_feedback("test prompt")

    # Should return error message with timeout details
    assert result == "Error generating LLM feedback: Request timed out"


@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_get_feedback_http_error(mock_model_class, mock_configure, monkeypatch):
    """Test get_feedback with HTTP error - covers HTTP request failure scenarios."""
    # Set up environment and mocks
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    # Simulate HTTP error
    http_error = Exception("HTTP 429: Rate limit exceeded")
    mock_model = Mock()
    mock_model.generate_content.side_effect = http_error
    mock_model_class.return_value = mock_model

    # Initialize client and call get_feedback
    client = LlmApiClient()
    result = client.get_feedback("test prompt")

    # Should return error message with HTTP error details
    assert result == "Error generating LLM feedback: HTTP 429: Rate limit exceeded"
