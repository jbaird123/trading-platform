import json
from unittest.mock import MagicMock

import pytest
from trading_platform.ai.llm_analysis.engine import LLMAnalysisEngine


def test_llm_engine_run():
    # 1. Arrange
    mock_client = MagicMock()
    mock_client.get_feedback.return_value = "This is mock feedback."
    dummy_brief = {"meta": {"run_id": "test1234"}}

    # 2. Act
    engine = LLMAnalysisEngine(brief_data=dummy_brief, client=mock_client)
    result = engine.run()

    # 3. Assert
    assert result == "This is mock feedback."

    # Verify the prompt passed to the client was correct
    mock_client.get_feedback.assert_called_once()
    call_args = mock_client.get_feedback.call_args
    prompt = call_args[0][0]
    assert "You are an expert trading strategist" in prompt
    assert json.dumps(dummy_brief, indent=2) in prompt


def test_llm_engine_missing_prompt(tmp_path, monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_client.get_feedback.return_value = "Should not be called"
    dummy_brief = {"meta": {"run_id": "test_missing_prompt"}}

    # Ensure no system_prompt.md exists
    engine_dir = tmp_path
    monkeypatch.setattr("pathlib.Path.parent", property(lambda self: engine_dir))
    # Remove system_prompt.md if present
    prompt_path = engine_dir / "system_prompt.md"
    if prompt_path.exists():
        prompt_path.unlink()

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        LLMAnalysisEngine(brief_data=dummy_brief, client=mock_client)
