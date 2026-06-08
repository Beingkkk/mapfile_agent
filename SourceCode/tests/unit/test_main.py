"""Tests for FastAPI WebSocket endpoint.

DC-036  plan-platform §5.1
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest

# Import main after adding backend to path
import main as main_module

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


class MockWebSocket:
    """Mock FastAPI WebSocket for testing."""

    def __init__(self):
        self.sent_messages: list[dict] = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        self.sent_messages.append(json.loads(text))

    async def send_json(self, data: dict):
        self.sent_messages.append(data)

    async def receive_text(self) -> str:
        return "{}"

    async def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear sessions dict before each test."""
    main_module.sessions.clear()
    yield
    main_module.sessions.clear()


class TestSessionManagement:
    def test_get_or_create_session(self):
        session = main_module.get_or_create_session("test-1")
        assert session.session_id == "test-1"
        assert session.params["__type__"] == "map"

    def test_get_existing_session(self):
        s1 = main_module.get_or_create_session("test-2")
        s2 = main_module.get_or_create_session("test-2")
        assert s1 is s2


class TestHandleMessage:
    @pytest.mark.anyio
    async def test_init_session(self):
        ws = MockWebSocket()
        msg = {"type": "init_session", "intent": "Create WMS map"}
        await main_module.handle_message(ws, msg, "session-1")

        assert len(ws.sent_messages) >= 1
        # Should receive tree_state
        tree_states = [m for m in ws.sent_messages if m.get("type") == "tree_state"]
        assert len(tree_states) >= 1
        session = main_module.sessions.get("session-1")
        assert session is not None
        assert session.history._initial_intent == "Create WMS map"

    @pytest.mark.anyio
    async def test_tree_update(self):
        ws = MockWebSocket()
        # First init session
        await main_module.handle_message(ws, {"type": "init_session"}, "session-2")

        # Then update
        await main_module.handle_message(
            ws,
            {"type": "tree_update", "updates": [{"path": "name", "value": "roads"}]},
            "session-2",
        )

        tree_states = [m for m in ws.sent_messages if m.get("type") == "tree_state"]
        assert len(tree_states) >= 2  # init + update
        session = main_module.sessions["session-2"]
        assert session.params.get("name") == "roads"

    @pytest.mark.anyio
    async def test_focus_change(self):
        ws = MockWebSocket()
        await main_module.handle_message(ws, {"type": "init_session"}, "session-3")

        await main_module.handle_message(
            ws,
            {"type": "focus_change", "path": "layers.0.name"},
            "session-3",
        )

        focus_states = [m for m in ws.sent_messages if m.get("type") == "focus_state"]
        assert len(focus_states) >= 1
        assert focus_states[0].get("focus_param") == "layers.0.name"

    @pytest.mark.anyio
    async def test_validate(self):
        ws = MockWebSocket()
        await main_module.handle_message(ws, {"type": "init_session"}, "session-4")

        await main_module.handle_message(ws, {"type": "validate"}, "session-4")

        val_results = [m for m in ws.sent_messages if m.get("type") == "validation_result"]
        assert len(val_results) >= 1
        assert "validation_state" in val_results[0]

        # Manual validate should also push tree_state so leaf-level errors are rendered.
        tree_states = [m for m in ws.sent_messages if m.get("type") == "tree_state"]
        assert len(tree_states) >= 2  # init + validate
        last_tree = tree_states[-1]
        assert "params_snapshot" in last_tree
        assert last_tree.get("validation_state") == val_results[0].get("validation_state")

    @pytest.mark.anyio
    async def test_set_service_types(self):
        ws = MockWebSocket()
        await main_module.handle_message(ws, {"type": "init_session"}, "session-5")

        await main_module.handle_message(
            ws,
            {"type": "set_service_types", "services": ["wms", "wfs"], "mapcache_enabled": True},
            "session-5",
        )

        session = main_module.sessions["session-5"]
        assert session.service_types == ["wms", "wfs"]
        assert session.mapcache_enabled is True

    @pytest.mark.anyio
    async def test_reset_session(self):
        ws = MockWebSocket()
        await main_module.handle_message(ws, {"type": "init_session"}, "session-6")
        main_module.sessions["session-6"].params["name"] = "old"

        await main_module.handle_message(ws, {"type": "reset_session"}, "session-6")

        session = main_module.sessions["session-6"]
        # Reset restores defaults; name gets its default value back ("MS"), not None
        assert session.params.get("name") != "old"

    @pytest.mark.anyio
    async def test_export_blocks_when_not_validated(self):
        ws = MockWebSocket()
        await main_module.handle_message(ws, {"type": "init_session"}, "session-7")

        await main_module.handle_message(ws, {"type": "export"}, "session-7")

        export_results = [m for m in ws.sent_messages if m.get("type") == "export_result"]
        assert len(export_results) >= 1
        assert export_results[0].get("success") is False

    @pytest.mark.anyio
    async def test_import_mapfile(self):
        ws = MockWebSocket()
        mapfile_text = '''MAP
            NAME "imported"
            STATUS ON
            EXTENT -180 -90 180 90
            LAYER
                NAME "l1"
                STATUS ON
                TYPE POLYGON
            END
        END'''
        await main_module.handle_message(
            ws,
            {"type": "import_mapfile", "content": mapfile_text},
            "session-8",
        )

        import_results = [m for m in ws.sent_messages if m.get("type") == "import_result"]
        assert len(import_results) >= 1
        assert import_results[0].get("success") is True

    @pytest.mark.anyio
    async def test_unknown_message_type_returns_error(self):
        ws = MockWebSocket()
        await main_module.handle_message(
            ws, {"type": "unknown_type"}, "session-9"
        )

        errors = [m for m in ws.sent_messages if m.get("type") == "error"]
        assert len(errors) >= 1

    @pytest.mark.anyio
    async def test_tree_state_format_matches_frontend_contract(self):
        """params_snapshot must be TreeNode structure, not raw mappyfile dict.

        Regression: backend used to send session.params ({"__type__": "map"})
        which lacks children/expanded/object_type that ObjectCard expects.
        """
        ws = MockWebSocket()
        await main_module.handle_message(ws, {"type": "init_session"}, "session-contract")

        tree_states = [m for m in ws.sent_messages if m.get("type") == "tree_state"]
        assert len(tree_states) >= 1
        snapshot = tree_states[0]["params_snapshot"]

        # Must be TreeNode structure, not raw mappyfile dict
        assert "__type__" not in snapshot, "snapshot must not be raw mappyfile dict"
        assert snapshot["object_type"] == "MAP"
        assert snapshot["path"] == "map"
        assert "id" in snapshot
        assert "expanded" in snapshot
        assert isinstance(snapshot["children"], list)

        # Each child must be TreeNode or TreeLeaf
        for child in snapshot["children"]:
            assert "id" in child
            assert "path" in child
            if "children" in child:
                # TreeNode
                assert "object_type" in child
                assert isinstance(child["children"], list)
            else:
                # TreeLeaf
                assert "key" in child
                assert "value" in child
                assert "value_type" in child
                assert "phase" in child
                assert "required" in child
                assert "custom" in child
