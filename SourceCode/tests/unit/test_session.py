"""Tests for ConfigSession."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/core is on PYTHONPATH
_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

import pytest

from session import ConfigSession
from template_mapper import TemplateMapper

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mapper():
    return TemplateMapper(str(RULES_PATH))


# ---------------------------------------------------------------------------
# Phase 1: Basic initialization
# ---------------------------------------------------------------------------


class TestConfigSessionInit:
    def test_default_params_is_map_dict(self, mapper):
        """ConfigSession with no params should initialise params as a mappyfile MAP dict."""
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.params is not None
        assert isinstance(session.params, dict)
        assert session.params.get("__type__") == "map"

    def test_service_types_default(self, mapper):
        """Default service_types should be ["wms"]."""
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.service_types == ["wms"]

    def test_mapcache_enabled_default(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.mapcache_enabled is False

    def test_validation_state_default(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.validation_state == "idle"

    def test_tree_auto_build(self, mapper):
        """__post_init__ should auto-build ConfigTree when tree is None."""
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.tree is not None
        assert session.tree.root.object_type == "MAP"

    def test_intent_message(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper, intent_message="Create WMS")
        assert session.intent_message == "Create WMS"

    def test_focus_param_default(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.focus_param is None

    def test_validation_errors_default(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        assert session.validation_errors == []

    def test_custom_params_preserved(self, mapper):
        """Custom params should be preserved and tree built from them."""
        custom = {"__type__": "map", "name": "test_map", "status": "on"}
        session = ConfigSession(session_id="test-1", mapper=mapper, params=custom)
        assert session.params["name"] == "test_map"
        assert session.tree.root.object_type == "MAP"


# ---------------------------------------------------------------------------
# Phase 2: Focus management
# ---------------------------------------------------------------------------


class TestConfigSessionFocus:
    def test_set_focus(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        session.set_focus("layers.0.name")
        assert session.focus_param == "layers.0.name"

    def test_set_focus_none(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        session.set_focus("layers.0.name")
        session.set_focus(None)
        assert session.focus_param is None

    def test_set_focus_resets_history_round_count(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        session.history.round_count = 3
        session.set_focus("layers.0.name")
        assert session.history.round_count == 0


# ---------------------------------------------------------------------------
# Phase 3: LLM updates
# ---------------------------------------------------------------------------


class TestConfigSessionApplyLlmUpdates:
    def test_apply_single_update(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        session.apply_llm_updates([{"path": "name", "value": "my_map"}])
        assert session.params["name"] == "my_map"

    def test_apply_multiple_updates(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        session.apply_llm_updates([
            {"path": "name", "value": "my_map"},
            {"path": "status", "value": "off"},
        ])
        assert session.params["name"] == "my_map"
        assert session.params["status"] == "off"

    def test_apply_nested_update(self, mapper):
        """Updates to nested params should write through to the correct nested dict."""
        params = {
            "__type__": "map",
            "layers": [
                {"__type__": "layer", "name": "old_name"},
            ],
        }
        session = ConfigSession(session_id="test-1", mapper=mapper, params=params)
        session.apply_llm_updates([{"path": "layers.0.name", "value": "new_name"}])
        assert session.params["layers"][0]["name"] == "new_name"

    def test_apply_update_rebuilds_tree(self, mapper):
        session = ConfigSession(session_id="test-1", mapper=mapper)
        old_root_id = session.tree.root.id
        session.apply_llm_updates([{"path": "name", "value": "my_map"}])
        # Tree should be rebuilt after updates
        assert session.tree.root.id == old_root_id  # root id stays "map"
        node = session.tree.get_node("name")
        assert node is not None
        assert node.value == "my_map"
