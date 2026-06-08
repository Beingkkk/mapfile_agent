"""PromptBuilder — assemble L0–L5 context for LLM prompts.

DC-018  plan-backend-llm §3.2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptBuilder:
    """Load _framework.j2 and render with L0–L5 context variables."""

    def __init__(self, templates_dir: str) -> None:
        path = Path(templates_dir)
        if not path.exists():
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

        self._env = Environment(
            loader=FileSystemLoader(str(path)),
            autoescape=select_autoescape(),
        )
        self._template = self._env.get_template("_framework.j2")

    def render(
        self,
        intent: str,
        map_snapshot: str,
        focus_param: str | None,
        context_summary: str,
        validation_errors: list[dict],
        recent_messages: str = "",
    ) -> str:
        """Render the full prompt with all L0–L5 context."""
        return self._template.render(
            intent=intent,
            map_snapshot=map_snapshot,
            focus_param=focus_param,
            context_summary=context_summary,
            validation_errors=validation_errors,
            recent_messages=recent_messages,
        )
