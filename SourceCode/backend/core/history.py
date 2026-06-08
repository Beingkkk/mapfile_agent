"""DialogueHistory — QA conversation history management.

DC-017  plan-backend-llm §3.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DialogueMessage:
    """A single message in the QA dialogue."""

    role: str  # user | bot | system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    intent: str | None = None
    focus_param: str | None = None


class DialogueHistory:
    """Hold QA messages and round counter.

    - Intent is preserved across focus changes.
    - Round count resets to 0 on focus change.
    - to_prompt_context caps at 6 rounds for token budget.
    """

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self._initial_intent: str | None = None
        self._current_focus: str | None = None
        self._round_count: int = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_intent(self, text: str) -> None:
        """Set the initial user intent as a system message."""
        self._initial_intent = text
        self.messages.append(
            {"role": "system", "content": f"User intent: {text}", "intent": text}
        )

    def set_focus(self, focus_param: str | None) -> None:
        """Set current focus parameter."""
        self._current_focus = focus_param

    def add_message(self, role: str, content: str) -> None:
        """Add a message and increment round count on bot responses."""
        self.messages.append(
            {
                "role": role,
                "content": content,
                "focus_param": self._current_focus,
            }
        )
        if role == "bot":
            self._round_count += 1

    def to_prompt_context(self) -> str:
        """Format recent messages for LLM prompt (max 6 rounds = 12 messages).

        Returns a string like:
            User intent: Create a WMS map...
            User: What about SRS?
            Bot: Use EPSG:3857
            ...
        """
        lines: list[str] = []

        # Always include intent/system messages
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        qa_msgs = [m for m in self.messages if m.get("role") in ("user", "bot")]

        for m in system_msgs:
            lines.append(m["content"])

        # Cap QA messages to last 6 rounds (12 messages)
        MAX_ROUNDS = 6
        capped_qa = qa_msgs[-(MAX_ROUNDS * 2) :]

        for m in capped_qa:
            prefix = "User" if m["role"] == "user" else "Bot"
            lines.append(f"{prefix}: {m['content']}")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def round_count(self) -> int:
        return self._round_count

    @round_count.setter
    def round_count(self, value: int) -> None:
        self._round_count = value

    # ─────────────────────────────────────────────────────────────────────────
    # Focus change handling
    # ─────────────────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Clear all QA messages but preserve system/intent messages.

        Used when user explicitly resets history context.
        Unlike reset_on_focus_change, this does NOT touch focus.
        """
        self._round_count = 0
        if self._initial_intent:
            self.messages = [
                m for m in self.messages
                if m.get("role") == "system" or m.get("intent") is not None
            ]
        else:
            self.messages.clear()

    def reset_on_focus_change(self) -> None:
        """Reset round counter when focus changes; preserve initial intent."""
        self._round_count = 0
        has_qa = any(m.get("role") in ("user", "bot") for m in self.messages)
        if has_qa:
            self.clear()
        self._current_focus = None
