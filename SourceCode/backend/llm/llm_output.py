"""LLMOutput — resilient JSON parsing for LLM responses.

DC-020  plan-backend-llm §3.4

Parse strategy (V2 validated):
    direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedOutput:
    """Structured result from LLM response parsing."""

    thought: str = ""
    action: str = "answer"  # answer | update | question
    params_update: list[dict] = None  # type: ignore[assignment]
    question: str = ""

    def __post_init__(self):
        if self.params_update is None:
            self.params_update = []


class LLMOutput:
    """Parse raw LLM text into structured ParsedOutput."""

    _VALID_ACTIONS = {"answer", "update", "question"}

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def parse(cls, raw: str) -> ParsedOutput:
        """Four-layer tolerant parsing with fallback."""
        if not raw or not raw.strip():
            return cls._fallback("")

        # Layer 1: direct JSON parse
        data = cls._try_direct_json(raw)
        if data is not None:
            return cls._build_parsed(data)

        # Layer 2: strip markdown code blocks
        data = cls._try_strip_codeblock(raw)
        if data is not None:
            return cls._build_parsed(data)

        # Layer 3: extract JSON from braces
        data = cls._try_brace_extract(raw)
        if data is not None:
            return cls._build_parsed(data)

        # Layer 4: json5 tolerant parse
        data = cls._try_json5_tolerant(raw)
        if data is not None:
            return cls._build_parsed(data)

        # Fallback: treat as plain text answer
        return cls._fallback(raw)

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 1: direct JSON
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _try_direct_json(cls, raw: str) -> dict | None:
        try:
            return json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 2: strip code blocks
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _try_strip_codeblock(cls, raw: str) -> dict | None:
        # Match ```json ... ``` or ``` ... ```
        pattern = r"```(?:json)?\s*(.*?)\s*```"
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            inner = match.group(1).strip()
            try:
                return json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 3: brace extract
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _try_brace_extract(cls, raw: str) -> dict | None:
        """Find the first {...} that parses as valid JSON."""
        # Find outermost balanced braces
        for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL):
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 4: json5 tolerant
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _try_json5_tolerant(cls, raw: str) -> dict | None:
        """Try to fix common JSON5 issues: single quotes, trailing commas."""
        cleaned = raw.strip()
        # Replace single quotes with double quotes (naïve but works for simple cases)
        cleaned = re.sub(r"'([^']*?)'", r'"\1"', cleaned)
        # Remove trailing commas before } or ]
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Fallback
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _fallback(cls, raw: str) -> ParsedOutput:
        return ParsedOutput(
            thought="",
            action="answer",
            params_update=[],
            question=raw.strip(),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Build ParsedOutput from dict
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def _build_parsed(cls, data: dict) -> ParsedOutput:
        action = data.get("action", "answer")
        if action not in cls._VALID_ACTIONS:
            action = "answer"

        params_update = data.get("params_update", [])
        if not isinstance(params_update, list):
            params_update = []

        return ParsedOutput(
            thought=data.get("thought", ""),
            action=action,
            params_update=params_update,
            question=data.get("question", ""),
        )
