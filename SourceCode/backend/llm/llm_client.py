"""LLMClient — Anthropic Claude API wrapper with retry logic.

DC-019  plan-backend-llm §3.3
"""

from __future__ import annotations

import time
from typing import Any

import anthropic


class LLMClient:
    """Synchronous wrapper around anthropic.Anthropic with exponential backoff."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        base_url: str | None = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._max_retries = max_retries
        self._last_usage: dict[str, int] = {}

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url is not None:
            kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**kwargs)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def chat(self, prompt: str) -> str:
        """Send prompt to LLM and return raw text response.

        Retries on API errors with exponential backoff (1s, 2s, 4s...).
        Raises the last exception if all retries are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    temperature=self._temperature,
                    system="You are a MapServer configuration assistant.",
                    messages=[{"role": "user", "content": prompt}],
                )
                # Record token usage
                if hasattr(response, "usage") and response.usage is not None:
                    self._last_usage = {
                        "input_tokens": getattr(response.usage, "input_tokens", 0),
                        "output_tokens": getattr(response.usage, "output_tokens", 0),
                    }
                # Extract text from content blocks
                for block in response.content:
                    if getattr(block, "type", None) == "text":
                        return block.text
                return ""

            except Exception as exc:  # noqa: BLE001
                last_exception = exc
                if attempt < self._max_retries - 1:
                    sleep_time = 2 ** attempt  # 1s, 2s, 4s...
                    time.sleep(sleep_time)

        if last_exception is not None:
            raise last_exception
        return ""

    @property
    def last_usage(self) -> dict[str, int]:
        """Return token usage from the last successful call."""
        return self._last_usage.copy()
