"""FastAPI WebSocket entry-point for MapGuide backend.

DC-036  plan-platform §3.5
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket

# Ensure backend/core and backend/llm are importable
_HERE = Path(__file__).resolve().parent
_CORE = _HERE / "core"
_LLM = _HERE / "llm"
_MAPCACHE = _HERE / "mapcache"
_sys = __import__("sys")
for p in (str(_HERE), str(_CORE), str(_LLM), str(_MAPCACHE)):
    if p not in _sys.path:
        _sys.path.insert(0, p)

from config_tree import ConfigTree
from export_service import ExportService
from history import DialogueHistory
from import_service import ImportService
from qa_service import QAService
from session import ConfigSession
from template_mapper import TemplateMapper
from validation import ValidationPipeline

from prompt_builder import PromptBuilder
from llm_client import LLMClient

_MAPCACHE_TEMPLATES = _HERE / "mapcache" / "templates"

# ─────────────────────────────────────────────────────────────────────────────
# Globals
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="MapGuide Backend")

RULES_PATH = _HERE.parent / "data" / "mapguide_rules.json"
TEMPLATES_DIR = _HERE / "llm" / "templates"
CONFIG_PATH = _HERE.parent / "config" / "config.json"


def _load_llm_config() -> dict[str, str]:
    """Load LLM config from config.json (fallback to env vars)."""
    cfg: dict[str, str] = {"api_key": "", "base_url": "", "model": ""}
    # 1. Try config.json
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            llm_cfg = data.get("llm", {})
            cfg["api_key"] = llm_cfg.get("auth_key", "")
            cfg["base_url"] = llm_cfg.get("base_url", "")
            cfg["model"] = llm_cfg.get("model_name", "")
        except (json.JSONDecodeError, OSError):
            pass
    # 2. Env vars override config.json
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        cfg["api_key"] = env_key
    env_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    if env_url:
        cfg["base_url"] = env_url
    return cfg

# Lazy-initialized singletons
_mapper: TemplateMapper | None = None
_pipeline: ValidationPipeline | None = None
_export_svc: ExportService | None = None
_import_svc: ImportService | None = None
_builder: PromptBuilder | None = None
_qa_svc: QAService | None = None

# In-memory session store
sessions: dict[str, ConfigSession] = {}


def _get_mapper() -> TemplateMapper:
    global _mapper
    if _mapper is None:
        _mapper = TemplateMapper(str(RULES_PATH))
    return _mapper


def _get_pipeline() -> ValidationPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ValidationPipeline(_get_mapper())
    return _pipeline


def _get_export_service() -> ExportService:
    global _export_svc
    if _export_svc is None:
        from mapcache.generator import MapCacheGenerator

        gen = MapCacheGenerator(str(_MAPCACHE_TEMPLATES))
        _export_svc = ExportService(mapcache_generator=gen)
    return _export_svc


def _get_import_service() -> ImportService:
    global _import_svc
    if _import_svc is None:
        _import_svc = ImportService(_get_mapper())
    return _import_svc


def _get_prompt_builder() -> PromptBuilder:
    global _builder
    if _builder is None:
        _builder = PromptBuilder(str(TEMPLATES_DIR))
    return _builder


def _get_qa_service(client: LLMClient | None = None) -> QAService:
    global _qa_svc
    if _qa_svc is None:
        cfg = _load_llm_config()
        api_key = cfg["api_key"]
        base_url = cfg["base_url"] or None
        model = cfg["model"] or None
        if client is None:
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            if model:
                kwargs["model"] = model
            client = LLMClient(**kwargs) if api_key else LLMClient(api_key="dummy")
        _qa_svc = QAService(
            session=None,  # set per-request
            pipeline=_get_pipeline(),
            mapper=_get_mapper(),
            client=client,
            builder=_get_prompt_builder(),
        )
    return _qa_svc


# ─────────────────────────────────────────────────────────────────────────────
# Session helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_session(session_id: str) -> ConfigSession:
    """Return existing session or create a fresh one."""
    if session_id not in sessions:
        sessions[session_id] = ConfigSession(
            session_id=session_id,
            mapper=_get_mapper(),
            service_types=["wms"],
        )
    return sessions[session_id]


def remove_session(session_id: str) -> None:
    sessions.pop(session_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    # Each connection is tied to a session_id (passed as query param)
    session_id = websocket.query_params.get("session_id", "default")

    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                await _send_error(websocket, "Invalid JSON")
                continue

            await handle_message(websocket, msg, session_id)
    except Exception:
        pass  # Client disconnected
    finally:
        remove_session(session_id)


# ─────────────────────────────────────────────────────────────────────────────
# Message dispatcher
# ─────────────────────────────────────────────────────────────────────────────

async def handle_message(
    websocket: WebSocket, msg: dict[str, Any], session_id: str
) -> None:
    """Route incoming WebSocket message to the appropriate handler."""
    msg_type = msg.get("type", "")
    session = get_or_create_session(session_id)

    handlers = {
        "init_session": _handle_init_session,
        "tree_update": _handle_tree_update,
        "tree_add_node": _handle_tree_add_node,
        "tree_remove_node": _handle_tree_remove_node,
        "tree_add_custom_prop": _handle_tree_add_custom_prop,
        "focus_change": _handle_focus_change,
        "question": _handle_question,
        "validate": _handle_validate,
        "export": _handle_export,
        "set_service_types": _handle_set_service_types,
        "reset_session": _handle_reset_session,
        "import_mapfile": _handle_import_mapfile,
        "clear_history": _handle_clear_history,
        "ping": _handle_ping,
    }

    handler = handlers.get(msg_type)
    if handler is None:
        await _send_error(websocket, f"Unknown message type: {msg_type}")
        return

    try:
        await handler(websocket, msg, session)
    except Exception as exc:
        await _send_error(websocket, str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_init_session(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    intent = msg.get("intent", "")
    if intent:
        session.history.set_intent(intent)
    await _send_tree_state(websocket, session)


async def _handle_tree_update(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    updates = msg.get("updates", [])
    for update in updates:
        path = update.get("path")
        value = update.get("value")
        if path is not None:
            session.tree.update_value(path, value, user_modified=True)

    # Run L1-L3 validation on each updated field
    pipeline = _get_pipeline()
    for update in updates:
        path = update.get("path")
        if path is not None:
            pipeline.validate_field(
                session.tree, path, session.service_types, full=False
            )

    await _send_tree_state(websocket, session)


async def _handle_tree_add_node(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    parent_path = msg.get("parent_path", "map")
    object_type = msg.get("object_type", "")
    if object_type:
        session.tree.add_object(parent_path, object_type)
    await _send_tree_state(websocket, session)


async def _handle_tree_remove_node(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    path = msg.get("path", "")
    if path:
        session.tree.remove_object(path)
    await _send_tree_state(websocket, session)


async def _handle_tree_add_custom_prop(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    session.tree.add_custom_property(
        parent_path=msg.get("parent_path", "map"),
        key=msg.get("key", ""),
        value=msg.get("value"),
        prop_type=msg.get("prop_type", "string"),
        desc=msg.get("desc", ""),
    )
    await _send_tree_state(websocket, session)


async def _handle_focus_change(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    path = msg.get("path")
    session.set_focus(path)
    await websocket.send_json({
        "type": "focus_state",
        "focus_param": session.focus_param,
    })


async def _handle_question(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    text = msg.get("text", "")
    if not text:
        await _send_error(websocket, "Empty question")
        return

    # Build a QAService with the current session injected
    qa = _get_qa_service()
    # Temporarily bind session
    original_session = qa.session
    qa.session = session
    try:
        result = qa.answer(text)
    finally:
        qa.session = original_session

    # Capture the focus_param that was active when this answer was generated
    answer_focus = session.focus_param

    await websocket.send_json({
        "type": "qa_result",
        "bot_message": result["answer"],
        "params_update": result["updates"],
        "validation_state": result["validation_state"],
        "validation_errors": result["errors"],
        "can_export": result["validation_state"] == "pass" and not result["errors"],
        "focus_param": answer_focus,
    })

    # If updates were applied, send tree_state as well
    if result["updates"]:
        await _send_tree_state(websocket, session)


async def _handle_validate(
    websocket: WebSocket, _msg: dict[str, Any], session: ConfigSession
) -> None:
    pipeline = _get_pipeline()
    result = pipeline.validate_tree(session.tree, session.service_types)
    session.validation_state = result.state
    session.validation_errors = result.errors
    await _send_validation_result(websocket, session)


async def _handle_export(
    websocket: WebSocket, _msg: dict[str, Any], session: ConfigSession
) -> None:
    try:
        files = _get_export_service().export(session)
        await websocket.send_json({
            "type": "export_result",
            "success": True,
            "files": [
                {"name": name, "content_base64": content.decode("utf-8")}
                for name, content in files.items()
            ],
        })
    except ValueError as exc:
        await websocket.send_json({
            "type": "export_result",
            "success": False,
            "files": [],
            "error": str(exc),
        })


async def _handle_set_service_types(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    services = msg.get("services", ["wms"])
    mapcache = msg.get("mapcache_enabled", False)
    session.service_types = services
    session.mapcache_enabled = mapcache

    # Ensure CACHE node exists when MapCache is enabled, remove when disabled
    if mapcache and "cache" not in session.params:
        session.params["cache"] = {"__type__": "cache"}
    elif not mapcache and "cache" in session.params:
        del session.params["cache"]

    # Rebuild tree with new service type filtering
    session.tree = ConfigTree(
        session.params, session.mapper, session.service_types
    )
    await _send_tree_state(websocket, session)


async def _handle_reset_session(
    websocket: WebSocket, _msg: dict[str, Any], session: ConfigSession
) -> None:
    sessions[session.session_id] = ConfigSession(
        session_id=session.session_id,
        mapper=_get_mapper(),
        service_types=["wms"],
    )
    await _send_tree_state(websocket, sessions[session.session_id])


async def _handle_import_mapfile(
    websocket: WebSocket, msg: dict[str, Any], session: ConfigSession
) -> None:
    content = msg.get("content", "")
    if not content:
        await websocket.send_json({
            "type": "import_result",
            "success": False,
            "error": "Empty content",
        })
        return

    try:
        new_session, _result = _get_import_service().import_mapfile(
            session.session_id, content
        )
        sessions[session.session_id] = new_session
        await websocket.send_json({
            "type": "import_result",
            "success": True,
        })
        await _send_tree_state(websocket, new_session)
    except Exception as exc:
        await websocket.send_json({
            "type": "import_result",
            "success": False,
            "error": str(exc),
        })


async def _handle_clear_history(
    websocket: WebSocket, _msg: dict[str, Any], session: ConfigSession
) -> None:
    session.history.clear()
    await websocket.send_json({"type": "history_cleared"})


async def _handle_ping(
    websocket: WebSocket, _msg: dict[str, Any], _session: ConfigSession
) -> None:
    await websocket.send_json({"type": "pong"})


# ─────────────────────────────────────────────────────────────────────────────
# Response helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _send_tree_state(websocket: WebSocket, session: ConfigSession) -> None:
    can_export = (
        session.validation_state == "pass" and not session.validation_errors
    )
    # Serialize ConfigTree to frontend-friendly TreeNode structure
    tree_data = session.tree.serialize() if session.tree else {}
    await websocket.send_json({
        "type": "tree_state",
        "params_snapshot": tree_data,
        "validation_state": session.validation_state,
        "validation_errors": session.validation_errors,
        "can_export": can_export,
        "focus_param": session.focus_param,
        "service_types": session.service_types,
        "mapcache_enabled": session.mapcache_enabled,
    })


async def _send_validation_result(
    websocket: WebSocket, session: ConfigSession
) -> None:
    can_export = (
        session.validation_state == "pass" and not session.validation_errors
    )
    await websocket.send_json({
        "type": "validation_result",
        "validation_state": session.validation_state,
        "validation_errors": session.validation_errors,
        "can_export": can_export,
    })


async def _send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json({
        "type": "error",
        "message": message,
    })
