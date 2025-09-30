import json
from pathlib import Path
from typing import Any, Dict

from .client import LlmApiClient


class LLMAnalysisEngine:
    """Orchestrates qualitative analysis of a backtest brief using an LLM."""

    def __init__(self, brief_data: Dict[str, Any], client: LlmApiClient):
        self._brief = brief_data
        self._client = client
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Loads the master system prompt from a file."""
        prompt_path = Path(__file__).parent / "system_prompt.md"
        return prompt_path.read_text()

    def _format_brief_for_prompt(self) -> str:
        """
        Formats the brief JSON into a string for the prompt, summarizing bulky
        lists to stay within token limits.
        """
        brief_copy = self._brief.copy()

        for key in ["trades", "skipped_trades"]:
            if key in brief_copy and isinstance(brief_copy[key], list):
                trades_list = brief_copy[key]
                if len(trades_list) > 10:  # pragma: no branch
                    summary = {
                        "total_trades": len(trades_list),
                        "first_5_trades": trades_list[:5],
                        "last_5_trades": trades_list[-5:],
                    }
                    brief_copy[key] = summary

        brief_copy.pop("field_definitions", None)

        return json.dumps(brief_copy, indent=2)

    def run(self) -> str:
        """Generates and returns the qualitative feedback from the LLM."""
        formatted_brief = self._format_brief_for_prompt()
        final_prompt = (
            self._prompt_template
            + "\n\n--- BACKTEST BRIEF JSON ---\n\n"
            + formatted_brief
        )
        return self._client.get_feedback(final_prompt)
