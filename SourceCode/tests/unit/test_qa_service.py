"""Tests for QAService.

DC-053  plan-platform §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

_BACKEND_LLM = Path(__file__).resolve().parent.parent.parent / "backend" / "llm"
if str(_BACKEND_LLM) not in sys.path:
    sys.path.insert(0, str(_BACKEND_LLM))

import pytest

from qa_service import QAService
from validation import ValidationResult


class TestQAServiceAnswer:
    def _make_service(self, raw_llm_response: str):
        """Build a QAService with all dependencies mocked."""
        session = MagicMock()
        session.history = MagicMock()
        session.history._initial_intent = "Create a WMS map"
        session.history.to_prompt_context.return_value = "User: Hello\nBot: Hi"
        session.focus_param = "layers.0.name"
        session.service_types = ["wms"]
        session.validation_state = "idle"
        session.validation_errors = []
        session.tree = MagicMock()
        session.params = {"__type__": "map", "name": "test"}
        session.apply_llm_updates = MagicMock()

        pipeline = MagicMock()
        pipeline.validate_tree.return_value = ValidationResult(state="pass", errors=[])

        mapper = MagicMock()
        mapper.get_llm_context_summary.return_value = "LAYER fields: ..."

        client = MagicMock()
        client.chat.return_value = raw_llm_response

        builder = MagicMock()
        builder.render.return_value = "rendered prompt"

        service = QAService(session, pipeline, mapper, client, builder)
        return service, session, pipeline, client, builder

    def test_answer_action_returns_dict(self):
        raw = '{"thought": "test", "action": "answer", "params_update": [], "question": "This is a WMS service."}'
        service, session, *_ = self._make_service(raw)

        result = service.answer("What is this?")

        assert result["action"] == "answer"
        assert result["answer"] == "This is a WMS service."
        assert result["updates"] == []
        session.history.add_message.assert_any_call("user", "What is this?")
        session.history.add_message.assert_any_call("bot", "This is a WMS service.")

    def test_update_action_applies_changes(self):
        raw = '{"thought": "Set name", "action": "update", "params_update": [{"path": "name", "value": "roads"}], "question": "Name set to roads"}'
        service, session, pipeline, *_ = self._make_service(raw)

        result = service.answer("Set the map name")

        assert result["action"] == "update"
        assert result["answer"] == "Name set to roads"
        assert len(result["updates"]) == 1
        session.apply_llm_updates.assert_called_once()
        pipeline.validate_tree.assert_called_once()
        # After validation, session state should be updated
        assert session.validation_state == "pass"

    def test_question_action_returns_question(self):
        raw = '{"thought": "Need info", "action": "question", "params_update": [], "question": "What data source?"}'
        service, session, *_ = self._make_service(raw)

        result = service.answer("I want to add a layer")

        assert result["action"] == "question"
        assert result["answer"] == "What data source?"
        # Should not apply updates
        session.apply_llm_updates.assert_not_called()

    def test_empty_params_update_no_changes(self):
        raw = '{"thought": "Nothing to do", "action": "update", "params_update": [], "question": "No changes"}'
        service, session, *_ = self._make_service(raw)

        result = service.answer("test")

        assert result["action"] == "update"
        # No updates to apply
        session.apply_llm_updates.assert_not_called()

    def test_llm_plain_text_fallback(self):
        raw = "This is just plain text without JSON."
        service, session, *_ = self._make_service(raw)

        result = service.answer("test")

        assert result["action"] == "answer"
        assert result["answer"] == raw

    def test_validation_errors_passed_to_result(self):
        raw = '{"thought": "test", "action": "answer", "params_update": [], "question": "ok"}'
        service, session, *_ = self._make_service(raw)
        session.validation_errors = [{"path": "name", "message": "Required"}]
        session.validation_state = "fail"

        result = service.answer("test")

        assert result["validation_state"] == "fail"
        assert len(result["errors"]) == 1

    def test_multiple_updates_applied(self):
        raw = '{"thought": "Set multiple", "action": "update", "params_update": [{"path": "name", "value": "roads"}, {"path": "status", "value": "ON"}], "question": "Done"}'
        service, session, *_ = self._make_service(raw)

        result = service.answer("test")

        assert len(result["updates"]) == 2
        assert session.apply_llm_updates.call_count == 1

    def test_builder_called_with_context(self):
        raw = '{"thought": "test", "action": "answer", "params_update": [], "question": "hi"}'
        service, session, _, _, builder = self._make_service(raw)

        service.answer("test")

        builder.render.assert_called_once()
        call_args = builder.render.call_args[1]
        assert call_args["intent"] == "Create a WMS map"
        assert call_args["focus_param"] == "layers.0.name"


class TestBuildMapSnapshot:
    def _make_service(self, params: dict):
        """Build a QAService with only params set."""
        session = MagicMock()
        session.params = params

        pipeline = MagicMock()
        mapper = MagicMock()
        client = MagicMock()
        builder = MagicMock()

        return QAService(session, pipeline, mapper, client, builder)

    def test_scalar_array_values_included(self):
        """Extent / projection / size arrays must show their scalar values."""
        service = self._make_service({
            "__type__": "map",
            "extent": [120, 30, 121, 31],
            "projection": ["init=epsg:4326"],
        })
        snapshot = service._build_map_snapshot()
        assert "[0]: 120" in snapshot
        assert "[1]: 30" in snapshot
        assert "[3]: 31" in snapshot
        assert "[0]: init=epsg:4326" in snapshot

    def test_nested_dict_in_list(self):
        """Layers (list of dicts) must render child keys."""
        service = self._make_service({
            "__type__": "map",
            "layers": [
                {"__type__": "layer", "name": "roads", "type": "line"},
            ],
        })
        snapshot = service._build_map_snapshot()
        assert "[0]:" in snapshot
        assert "name: roads" in snapshot
        assert "type: line" in snapshot
        assert "__type__" not in snapshot

    def test_none_values_filtered(self):
        """None values should not appear in snapshot to reduce noise."""
        service = self._make_service({
            "__type__": "map",
            "name": "test",
            "debug": None,
        })
        snapshot = service._build_map_snapshot()
        assert "name: test" in snapshot
        assert "debug" not in snapshot

    def test_underscore_keys_skipped(self):
        """_custom and other underscore keys must be hidden."""
        service = self._make_service({
            "__type__": "map",
            "name": "test",
            "_custom": {"foo": {"value": "bar", "type": "string"}},
        })
        snapshot = service._build_map_snapshot()
        assert "name: test" in snapshot
        assert "_custom" not in snapshot

    def test_empty_params_returns_placeholder(self):
        """Empty params (only __type__) should return placeholder."""
        service = self._make_service({"__type__": "map"})
        snapshot = service._build_map_snapshot()
        assert snapshot == "(empty map)"
