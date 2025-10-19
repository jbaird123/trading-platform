"""Tests for LLM API client."""

from unittest.mock import MagicMock, patch

import pytest


def test_llm_client_default_provider():
    """Test LlmApiClient defaults to gemini provider."""
    # Validates: [REQ-LLM-001] Default provider is gemini
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.genai"
    ):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        client = LlmApiClient()
        assert client.provider == "gemini"


def test_llm_client_env_override():
    """Test LlmApiClient respects LLM_PROVIDER env var."""
    # Validates: [REQ-LLM-002] Environment variable override
    with patch.dict(
        "os.environ",
        {"LLM_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"},
        clear=True,
    ), patch("trading_platform.ai.llm_analysis.client.Anthropic"):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        client = LlmApiClient(provider="gemini")
        assert client.provider == "claude"


def test_llm_client_invalid_provider():
    """Test LlmApiClient raises error for invalid provider."""
    # Validates: [REQ-LLM-003] Validate provider
    with patch.dict("os.environ", {}, clear=True):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        with pytest.raises(ValueError, match="Unknown provider: invalid"):
            LlmApiClient(provider="invalid")


def test_init_gemini_success():
    """Test Gemini initialization with valid API key."""
    # Validates: [REQ-LLM-004] Initialize Gemini client
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.genai"
    ) as mock_genai:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        client = LlmApiClient(provider="gemini")

        assert client.provider == "gemini"
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once()


def test_init_gemini_missing_api_key():
    """Test Gemini initialization fails without API key."""
    # Validates: [REQ-LLM-005] Validate Gemini API key
    with patch.dict("os.environ", {}, clear=True):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        with pytest.raises(
            ValueError, match="GEMINI_API_KEY environment variable not set"
        ):
            LlmApiClient(provider="gemini")


def test_init_openai_success():
    """Test OpenAI initialization with valid API key."""
    # Validates: [REQ-LLM-006] Initialize OpenAI client
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.OpenAI"
    ) as mock_openai:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        client = LlmApiClient(provider="openai")

        assert client.provider == "openai"
        mock_openai.assert_called_once_with(api_key="test-key")


def test_init_openai_missing_api_key():
    """Test OpenAI initialization fails without API key."""
    # Validates: [REQ-LLM-007] Validate OpenAI API key
    with patch.dict("os.environ", {}, clear=True):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        with pytest.raises(
            ValueError, match="OPENAI_API_KEY environment variable not set"
        ):
            LlmApiClient(provider="openai")


def test_init_claude_success():
    """Test Claude initialization with valid API key."""
    # Validates: [REQ-LLM-008] Initialize Claude client
    with patch.dict("os.environ", {"CLAUDE_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.Anthropic"
    ) as mock_anthropic:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        client = LlmApiClient(provider="claude")

        assert client.provider == "claude"
        mock_anthropic.assert_called_once_with(api_key="test-key")


def test_init_claude_missing_api_key():
    """Test Claude initialization fails without API key."""
    # Validates: [REQ-LLM-009] Validate Claude API key
    with patch.dict("os.environ", {}, clear=True):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        with pytest.raises(
            ValueError, match="CLAUDE_API_KEY environment variable not set"
        ):
            LlmApiClient(provider="claude")


def test_get_feedback_gemini():
    """Test get_feedback with Gemini provider."""
    # Validates: [REQ-LLM-010] Get Gemini feedback
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.genai"
    ) as mock_genai:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.text = "Gemini response text"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = LlmApiClient(provider="gemini")
        result = client.get_feedback("test prompt")

        assert result == "Gemini response text"
        mock_model.generate_content.assert_called_once_with("test prompt")


def test_get_feedback_gemini_no_text():
    """Test get_feedback handles Gemini response without text."""
    # Validates: [REQ-LLM-011] Handle Gemini empty response
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.genai"
    ) as mock_genai:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock Gemini response without text attribute
        mock_response = MagicMock(spec=[])  # No attributes
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = LlmApiClient(provider="gemini")
        result = client.get_feedback("test prompt")

        assert "Error: LLM response did not contain text" in result


def test_get_feedback_openai():
    """Test get_feedback with OpenAI provider."""
    # Validates: [REQ-LLM-012] Get OpenAI feedback
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.OpenAI"
    ) as mock_openai_class:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock OpenAI response
        mock_message = MagicMock()
        mock_message.content = "OpenAI response text"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LlmApiClient(provider="openai")
        result = client.get_feedback("test prompt")

        assert result == "OpenAI response text"
        mock_client.chat.completions.create.assert_called_once()


def test_get_feedback_openai_empty_content():
    """Test get_feedback handles OpenAI empty content."""
    # Validates: [REQ-LLM-013] Handle OpenAI empty response
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.OpenAI"
    ) as mock_openai_class:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock OpenAI response with None content
        mock_message = MagicMock()
        mock_message.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LlmApiClient(provider="openai")
        result = client.get_feedback("test prompt")

        assert result == "Error: Empty response"


def test_get_feedback_openai_no_choices():
    """Test get_feedback handles OpenAI response without choices."""
    # Validates: [REQ-LLM-014] Handle OpenAI no choices
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.OpenAI"
    ) as mock_openai_class:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock OpenAI response with empty choices
        mock_response = MagicMock()
        mock_response.choices = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LlmApiClient(provider="openai")
        result = client.get_feedback("test prompt")

        assert "Error: LLM response did not contain text" in result


def test_get_feedback_claude():
    """Test get_feedback with Claude provider."""
    # Validates: [REQ-LLM-015] Get Claude feedback
    with patch.dict("os.environ", {"CLAUDE_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.Anthropic"
    ) as mock_anthropic_class:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock Claude response
        mock_text_block = MagicMock()
        mock_text_block.text = "Claude response text"
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LlmApiClient(provider="claude")
        result = client.get_feedback("test prompt")

        assert result == "Claude response text"
        mock_client.messages.create.assert_called_once()


def test_get_feedback_claude_empty_content():
    """Test get_feedback handles Claude empty content."""
    # Validates: [REQ-LLM-016] Handle Claude empty response
    with patch.dict("os.environ", {"CLAUDE_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.Anthropic"
    ) as mock_anthropic_class:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock Claude response with empty content
        mock_response = MagicMock()
        mock_response.content = []

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LlmApiClient(provider="claude")
        result = client.get_feedback("test prompt")

        assert "Error: LLM response did not contain text" in result


def test_get_feedback_exception_handling():
    """Test get_feedback handles exceptions gracefully."""
    # Validates: [REQ-LLM-017] Handle API exceptions
    with patch.dict("os.environ", {"CLAUDE_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.Anthropic"
    ) as mock_anthropic_class:
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        # Mock exception during API call
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_anthropic_class.return_value = mock_client

        client = LlmApiClient(provider="claude")
        result = client.get_feedback("test prompt")

        assert "Error generating LLM feedback: API error" in result


def test_get_feedback_unknown_provider_fallback():
    """Test get_feedback handles unknown provider in get_feedback path."""
    # Validates: [REQ-LLM-018] Handle unknown provider at runtime
    with patch.dict("os.environ", {"CLAUDE_API_KEY": "test-key"}, clear=True), patch(
        "trading_platform.ai.llm_analysis.client.Anthropic"
    ):
        from trading_platform.ai.llm_analysis.client import LlmApiClient

        client = LlmApiClient(provider="claude")
        # Manually set to unknown provider to test fallback
        client.provider = "unknown"
        result = client.get_feedback("test prompt")

        assert "Error: Unknown provider unknown" in result
