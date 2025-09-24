import os

import google.generativeai as genai


class LlmApiClient:
    """A client to handle communication with the Google Gemini API."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel("gemini-pro")

    def get_feedback(self, prompt: str) -> str:
        """Sends a prompt to the LLM and returns the text response."""
        try:
            response = self._model.generate_content(prompt)
            text = getattr(response, "text", None)
            if isinstance(text, str):
                return text
            return "Error: LLM response did not contain text."
        except Exception as e:
            # Basic error handling, can be enhanced later
            return f"Error generating LLM feedback: {e}"
