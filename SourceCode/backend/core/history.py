"""DialogueHistory — minimal placeholder for ConfigSession dependency.

Full implementation belongs to plan-backend-llm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DialogueHistory:
    """Hold QA messages and round counter."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    round_count: int = 0
    _initial_intent: str | None = None

    def reset_on_focus_change(self) -> None:
        """Reset round counter when focus changes; preserve initial intent."""
        self.round_count = 0
        # Keep messages that contain the initial intent if any
        if self._initial_intent:
            self.messages = [
                m for m in self.messages if m.get("role") == "system" or m.get("intent")
            ]
        else:
            self.messages.clear()
