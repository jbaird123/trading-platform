import os
from typing import Literal

import google.generativeai as genai
from anthropic import Anthropic
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from openai import OpenAI

LLMProvider = Literal["gemini", "openai", "claude"]


class LlmApiClient:
    """A client to handle communication with multiple LLM providers."""

    def __init__(self, provider: LLMProvider = "claude"):
        """
        Initialize the LLM client with the specified provider.

        Args:
            provider: The LLM provider to use ("gemini", "openai", or "claude").
                     Defaults to "claude". Can also be set via LLM_PROVIDER env var.
        """
        # Allow environment variable override
        self.provider = os.getenv("LLM_PROVIDER", provider).lower()

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "claude":
            self._init_claude()
        else:
            raise ValueError(
                f"Unknown provider: {self.provider}. "
                f"Must be one of: gemini, openai, claude"
            )

    def _init_gemini(self):
        """Initialize Google Gemini client."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)

        # Configure safety settings to be more permissive
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        self._gemini_model = genai.GenerativeModel(
            "gemini-2.5-pro", safety_settings=safety_settings
        )

    def _init_openai(self):
        """Initialize OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self._openai_client = OpenAI(api_key=api_key)

    def _init_claude(self):
        """Initialize Anthropic Claude client."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        self._claude_client = Anthropic(api_key=api_key)

    def get_feedback(self, prompt: str) -> str:
        """Sends a prompt to the configured LLM and returns the text response."""
        try:
            if self.provider == "gemini":
                return self._get_gemini_feedback(prompt)
            elif self.provider == "openai":
                return self._get_openai_feedback(prompt)
            elif self.provider == "claude":
                return self._get_claude_feedback(prompt)
            else:
                return f"Error: Unknown provider {self.provider}"
        except Exception as e:
            return f"Error generating LLM feedback: {e}"

    def _get_gemini_feedback(self, prompt: str) -> str:
        """Get feedback from Gemini."""
        response = self._gemini_model.generate_content(prompt)
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        return "Error: LLM response did not contain text."

    def _get_openai_feedback(self, prompt: str) -> str:
        """Get feedback from OpenAI."""
        response = self._openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )

        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or "Error: Empty response"

        return "Error: LLM response did not contain text."

    def _get_claude_feedback(self, prompt: str) -> str:
        """Get feedback from Claude."""
        response = self._claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        if response.content and len(response.content) > 0:
            first_content = response.content[0]
            if hasattr(first_content, "text"):
                return first_content.text
            else:
                return f"Error: Unexpected content type: {type(first_content)}"

        return "Error: LLM response did not contain text."
