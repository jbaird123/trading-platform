import pytest
from trading_platform.ai.llm_analysis.client import LlmApiClient


def test_llm_api_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable not set"):
        LlmApiClient()
