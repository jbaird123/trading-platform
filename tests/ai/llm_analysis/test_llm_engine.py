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


def test_llm_engine_large_trade_list_summarization():
    """Test that trade lists with >10 items are summarized to save tokens."""
    # Arrange
    mock_client = MagicMock()
    mock_client.get_feedback.return_value = "Mock feedback for large trade list"

    # Create brief with >10 trades and >10 skipped_trades
    large_trades = [{"trade_id": i, "pnl": i * 100} for i in range(15)]
    large_skipped = [{"skip_id": i, "reason": f"blackout_{i}"} for i in range(12)]
    brief_with_large_lists = {
        "meta": {"run_id": "large_test"},
        "trades": large_trades,
        "skipped_trades": large_skipped,
    }

    # Act
    engine = LLMAnalysisEngine(brief_data=brief_with_large_lists, client=mock_client)
    result = engine.run()

    # Assert
    assert result == "Mock feedback for large trade list"

    # Verify the prompt was called and contains summarized data
    mock_client.get_feedback.assert_called_once()
    call_args = mock_client.get_feedback.call_args
    prompt = call_args[0][0]

    # The prompt should contain summarized structure, not all 15 trades
    assert "total_trades" in prompt
    assert "first_5_trades" in prompt
    assert "last_5_trades" in prompt

    # Parse the JSON in the prompt to verify summarization
    brief_json_start = prompt.find("{")
    brief_json = prompt[brief_json_start:]
    parsed = json.loads(brief_json)

    # Verify trades were summarized
    assert isinstance(parsed["trades"], dict)
    assert parsed["trades"]["total_trades"] == 15
    assert len(parsed["trades"]["first_5_trades"]) == 5
    assert len(parsed["trades"]["last_5_trades"]) == 5

    # Verify skipped_trades were summarized
    assert isinstance(parsed["skipped_trades"], dict)
    assert parsed["skipped_trades"]["total_trades"] == 12
    assert len(parsed["skipped_trades"]["first_5_trades"]) == 5
    assert len(parsed["skipped_trades"]["last_5_trades"]) == 5
