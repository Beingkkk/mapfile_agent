"""Tests for DialogueHistory.

DC-017  plan-backend-llm §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

import pytest

from history import DialogueHistory, DialogueMessage


class TestDialogueHistory:
    def test_init_state(self):
        h = DialogueHistory()
        assert h.round_count == 0
        assert h.messages == []
        assert h._initial_intent is None

    def test_set_intent(self):
        h = DialogueHistory()
        h.set_intent("Create a WMS map for roads")
        assert h._initial_intent == "Create a WMS map for roads"
        assert len(h.messages) == 1
        assert h.messages[0]["role"] == "system"
        assert "roads" in h.messages[0]["content"]

    def test_add_message_increments_round(self):
        h = DialogueHistory()
        h.add_message("user", "Hello")
        assert h.round_count == 0  # first user msg doesn't count as a round
        h.add_message("bot", "Hi there")
        assert h.round_count == 1
        h.add_message("user", "Question 2")
        assert h.round_count == 1
        h.add_message("bot", "Answer 2")
        assert h.round_count == 2

    def test_reset_on_focus_change(self):
        h = DialogueHistory()
        h.set_intent("Test intent")
        h.add_message("user", "Q1")
        h.add_message("bot", "A1")
        assert h.round_count == 1
        assert len(h.messages) == 3  # system + user + bot

        h.reset_on_focus_change()
        assert h.round_count == 0
        # Should keep system/intent messages
        assert len(h.messages) == 1
        assert h.messages[0]["role"] == "system"

    def test_reset_without_intent_clears_all(self):
        h = DialogueHistory()
        h.add_message("user", "Q1")
        h.add_message("bot", "A1")
        assert h.round_count == 1

        h.reset_on_focus_change()
        assert h.round_count == 0
        assert h.messages == []

    def test_to_prompt_context_capped_at_6_rounds(self):
        h = DialogueHistory()
        h.set_intent("Intent")
        for i in range(10):
            h.add_message("user", f"Q{i}")
            h.add_message("bot", f"A{i}")
        ctx = h.to_prompt_context()
        # Should only include last 6 rounds (12 messages) + system
        lines = ctx.strip().split("\n")
        # Count bot responses in context
        bot_count = ctx.count("Bot:")
        assert bot_count <= 6

    def test_to_prompt_context_format(self):
        h = DialogueHistory()
        h.set_intent("Create a map")
        h.add_message("user", "What about SRS?")
        h.add_message("bot", "Use EPSG:3857")
        ctx = h.to_prompt_context()
        assert "Create a map" in ctx
        assert "What about SRS?" in ctx
        assert "Use EPSG:3857" in ctx

    def test_focus_param_tracking(self):
        h = DialogueHistory()
        h.set_focus("layers.0.name")
        assert h._current_focus == "layers.0.name"

    def test_add_message_without_intent(self):
        h = DialogueHistory()
        h.add_message("user", "Just a question")
        assert h.round_count == 0
        assert len(h.messages) == 1
        assert h.messages[0]["role"] == "user"

    def test_round_count_property_readonly(self):
        h = DialogueHistory()
        # round_count is a property, should be readable
        assert h.round_count == 0


class TestDialogueMessage:
    def test_create(self):
        m = DialogueMessage(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"
        assert m.intent is None
        assert m.focus_param is None

    def test_with_intent(self):
        m = DialogueMessage(role="system", content="intent", intent="Create map")
        assert m.intent == "Create map"
