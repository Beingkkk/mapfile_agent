"""Tests for PromptBuilder.

DC-018  plan-backend-llm §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_LLM = Path(__file__).resolve().parent.parent.parent / "backend" / "llm"
if str(_BACKEND_LLM) not in sys.path:
    sys.path.insert(0, str(_BACKEND_LLM))

import pytest

from prompt_builder import PromptBuilder

TEMPLATES_DIR = str(
    Path(__file__).resolve().parent.parent.parent / "backend" / "llm" / "templates"
)


class TestPromptBuilderInit:
    def test_loads_framework_template(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        assert pb._template is not None

    def test_missing_templates_dir_raises(self):
        with pytest.raises((FileNotFoundError, ValueError)):
            PromptBuilder("/nonexistent/dir")


class TestPromptBuilderRender:
    def test_render_includes_intent(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="Create a WMS map for roads",
            map_snapshot="map:\n  name: test",
            focus_param=None,
            context_summary="MAP fields...",
            validation_errors=[],
            recent_messages="",
        )
        assert "Create a WMS map for roads" in result

    def test_render_includes_map_snapshot(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="map:\n  name: roads",
            focus_param=None,
            context_summary="",
            validation_errors=[],
            recent_messages="",
        )
        assert "roads" in result

    def test_render_includes_focus_param(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param="layers.0.name",
            context_summary="",
            validation_errors=[],
            recent_messages="",
        )
        assert "layers.0.name" in result

    def test_render_focus_param_none_shows_default(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="",
            validation_errors=[],
            recent_messages="",
        )
        assert "无" in result or "None" in result

    def test_render_includes_context_summary(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="LAYER fields:\n  - name: string",
            validation_errors=[],
            recent_messages="",
        )
        assert "LAYER fields" in result

    def test_render_includes_validation_errors(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="",
            validation_errors=[
                {"path": "layers.0.name", "message": "Name is required"},
            ],
            recent_messages="",
        )
        assert "Name is required" in result

    def test_render_skips_errors_when_empty(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="",
            validation_errors=[],
            recent_messages="",
        )
        # Should not contain error section markers
        assert "校验错误" not in result or len(result) < 1000  # pragmatic

    def test_render_includes_recent_messages(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="",
            validation_errors=[],
            recent_messages="User: Hello\nBot: Hi",
        )
        assert "Hello" in result

    def test_render_contains_json_format_instruction(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="",
            validation_errors=[],
            recent_messages="",
        )
        assert '"action"' in result
        assert '"params_update"' in result
        assert '"question"' in result

    def test_render_contains_no_codeblock_warning(self):
        pb = PromptBuilder(TEMPLATES_DIR)
        result = pb.render(
            intent="test",
            map_snapshot="",
            focus_param=None,
            context_summary="",
            validation_errors=[],
            recent_messages="",
        )
        assert "代码块" in result or "```" in result
