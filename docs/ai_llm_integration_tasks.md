# AI Module: LLM Integration Implementation Plan

**Objective:** This document provides a precise, ordered set of tasks for a developer to implement the new `LLMAnalysisEngine`, which will provide optional, qualitative feedback on backtest results using a Large Language Model.

---

## 1. Task: Add and Isolate the LLM Client

- [ ] **1.1** **Action:** Add the `google-generativeai` library to the project's dependencies.
    -   Run the command: `poetry add google-generativeai`.
- [ ] **1.2** **File to Create:** `src/trading_platform/ai/llm_analysis/client.py`
- [ ] **1.3** **Action:** Create an API client to encapsulate all interaction with the external LLM service.
    ```python
    import os
    import google.generativeai as genai

    class LlmApiClient:
        """A client to handle communication with the Google Gemini API."""

        def __init__(self):
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set.")
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel('gemini-pro')

        def get_feedback(self, prompt: str) -> str:
            """Sends a prompt to the LLM and returns the text response."""
            try:
                response = self._model.generate_content(prompt)
                return response.text
            except Exception as e:
                # Basic error handling, can be enhanced later
                return f"Error generating LLM feedback: {e}"

    ```
- [ ] **1.4** **File to Create:** `tests/ai/llm_analysis/test_client.py`
- [ ] **1.5** **Action:** Add a test to verify that the client correctly raises a `ValueError` if the `GEMINI_API_KEY` is not set.

## 2. Task: Create the Master System Prompt

- [ ] **2.1** **File to Create:** `src/trading_platform/ai/llm_analysis/system_prompt.md`
- [ ] **2.2** **Action:** Add the following content to the file. This will be the master prompt that defines the LLM's persona and goal.
    ```markdown
    You are an expert trading strategist and quantitative analyst. You are reviewing a backtest report for a trading strategy. The report is provided in a comprehensive JSON format.

    Your task is to provide a high-level, qualitative critique of the strategy's performance and structure. Do not simply repeat the metrics from the JSON. Instead, focus on identifying potential structural flaws, logical disconnects, and areas for deeper investigation.

    Specifically, please address the following points in your review:
    1.  **Overall Narrative:** What is the story of this backtest? Is it a story of consistent small wins, a few large wins, or death by a thousand cuts?
    2.  **Structural Integrity:** Does the strategy seem logically sound? For example, if it is a trend-following strategy, does it perform well in trending regimes? Is there a clear connection between the indicators used and the entry/exit signals?
    3.  **Risk and Ruin:** Based on the drawdown metrics and trade distribution, does this strategy exhibit risky behavior? Comment on the risk/reward profile.
    4.  **Potential for Curve-Fitting:** Are there any signs that this strategy might be over-optimized or "curve-fit" to the historical data? For example, are the parameters very specific or is the performance highly concentrated in a specific period?
    5.  **Actionable Next Steps:** Based on your analysis, what is the single most important question the strategy developer should investigate next?

    Provide your feedback in a clear, concise Markdown format.
    ```

## 3. Task: Implement the `LLMAnalysisEngine`

- [ ] **3.1** **File to Create:** `src/trading_platform/ai/llm_analysis/engine.py`
- [ ] **3.2** **Action:** Create the engine that orchestrates the analysis.
    ```python
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
            """Formats the brief JSON into a string for the prompt."""
            # We can enhance this later, but for now, a pretty-printed JSON is fine.
            return json.dumps(self._brief, indent=2)

        def run(self) -> str:
            """Generates and returns the qualitative feedback from the LLM."""
            formatted_brief = self._format_brief_for_prompt()
            final_prompt = (
                self._prompt_template
                + "\n\n--- BACKTEST BRIEF JSON ---\n\n"
                + formatted_brief
            )
            return self._client.get_feedback(final_prompt)

    ```

## 4. Task: Integrate into the CLI

- [ ] **4.1** **File to Modify:** `src/trading_platform/cli.py`
- [ ] **4.2** **Action:**
    1.  In the `main` function, find the `ai-diagnose` sub-parser (`pad`).
    2.  Add the following argument to it:
        ```python
        pad.add_argument(
            "--qualitative-report",
            action="store_true",
            help="Generate a qualitative report using an external LLM. "
                 "WARNING: This sends run data to a third-party API and may incur costs.",
        )
        ```
    3.  In the `cmd_ai_diagnose` function, after the existing reports are saved, add the following block of code:
        ```python
        if args.qualitative_report:
            print("Generating qualitative report via LLM...")
            try:
                from trading_platform.ai.llm_analysis.client import LlmApiClient
                from trading_platform.ai.llm_analysis.engine import LLMAnalysisEngine

                client = LlmApiClient()
                llm_engine = LLMAnalysisEngine(brief_data=brief_data, client=client)
                feedback = llm_engine.run()
                report_path = output_dir / "ai_qualitative_report.md"
                report_path.write_text(feedback)
                print(f"Qualitative report saved to {report_path}")
            except Exception as e:
                print(f"Could not generate qualitative report: {e}", file=sys.stderr)
        ```

## 5. Task: Add Tests for the New Components

- [ ] **5.1** **File to Create:** `tests/ai/llm_analysis/test_llm_engine.py`
- [ ] **5.2** **Action:** Add tests to verify the engine's logic without making real API calls.
    ```python
    import json
    from unittest.mock import MagicMock
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
    ```
- [ ] **5.3** **File to Modify:** `tests/cli/test_cli_ai_diagnose.py`
- [ ] **5.4** **Action:** Add a test to verify the CLI flag integration.
    ```python
    from unittest.mock import patch
    from argparse import Namespace
    from pathlib import Path
    import json
    from trading_platform.cli import cmd_ai_diagnose

    def test_cmd_ai_diagnose_qualitative_report_flag(tmp_path: Path):
        # 1. Create a dummy brief.json
        brief_content = {"meta": {"run_id": "test_run_123"}}
        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps(brief_content))

        # 2. Simulate command-line arguments with the new flag
        ns = Namespace(brief=str(brief_path), qualitative_report=True)

        # 3. Mock the LLM client to avoid real API calls
        with patch("trading_platform.cli.LlmApiClient") as mock_api_client:
            # Configure the mock instance
            mock_instance = mock_api_client.return_value
            mock_instance.get_feedback.return_value = "Mocked LLM response"

            # 4. Call the command
            with patch("builtins.print") as mock_print:
                return_code = cmd_ai_diagnose(ns)

                # 5. Assertions
                assert return_code == 0
                qualitative_report_path = tmp_path / "ai_qualitative_report.md"
                assert qualitative_report_path.exists()
                assert qualitative_report_path.read_text() == "Mocked LLM response"
                mock_print.assert_any_call("Generating qualitative report via LLM...")
                mock_print.assert_any_call(f"Qualitative report saved to {qualitative_report_path}")
    ```
