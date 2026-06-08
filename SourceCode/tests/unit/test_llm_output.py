"""Tests for LLMOutput parsing.

DC-020  plan-backend-llm §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_LLM = Path(__file__).resolve().parent.parent.parent / "backend" / "llm"
if str(_BACKEND_LLM) not in sys.path:
    sys.path.insert(0, str(_BACKEND_LLM))

import pytest

from llm_output import LLMOutput, ParsedOutput


class TestParsedOutput:
    def test_dataclass_fields(self):
        po = ParsedOutput(
            thought="test",
            action="answer",
            params_update=[],
            question="hello",
        )
        assert po.thought == "test"
        assert po.action == "answer"
        assert po.params_update == []
        assert po.question == "hello"


class TestLLMOutputDirectJson:
    def test_valid_json_update(self):
        raw = '{"thought": "Set type", "action": "update", "params_update": [{"path": "layers.0.type", "value": "polygon"}], "question": "已修改为 polygon"}'
        result = LLMOutput.parse(raw)
        assert result.action == "update"
        assert len(result.params_update) == 1
        assert result.params_update[0]["path"] == "layers.0.type"
        assert result.question == "已修改为 polygon"

    def test_valid_json_answer(self):
        raw = '{"thought": "Explain", "action": "answer", "params_update": [], "question": "这是一个 WMS 服务"}'
        result = LLMOutput.parse(raw)
        assert result.action == "answer"
        assert result.params_update == []
        assert result.question == "这是一个 WMS 服务"

    def test_valid_json_question(self):
        raw = '{"thought": "Need more info", "action": "question", "params_update": [], "question": "请提供数据源类型"}'
        result = LLMOutput.parse(raw)
        assert result.action == "question"


class TestLLMOutputStripCodeblock:
    def test_json_in_codeblock(self):
        raw = '```json\n{"thought": "test", "action": "answer", "params_update": [], "question": "hi"}\n```'
        result = LLMOutput.parse(raw)
        assert result.action == "answer"
        assert result.question == "hi"

    def test_json_in_codeblock_no_language(self):
        raw = '```\n{"thought": "test", "action": "answer", "params_update": [], "question": "hello"}\n```'
        result = LLMOutput.parse(raw)
        assert result.question == "hello"


class TestLLMOutputBraceExtract:
    def test_text_with_json_embedded(self):
        raw = 'Sure, here is the result:\n\n{"thought": "test", "action": "update", "params_update": [{"path": "name", "value": "test"}], "question": "done"}\n\nHope this helps!'
        result = LLMOutput.parse(raw)
        assert result.action == "update"
        assert result.params_update[0]["value"] == "test"

    def test_multiple_braces_takes_first(self):
        raw = 'Text {"a": 1} more {"thought": "x", "action": "answer", "params_update": [], "question": "y"}'
        result = LLMOutput.parse(raw)
        # First valid JSON object should be extracted
        assert result.action == "answer"


class TestLLMOutputJson5Tolerant:
    def test_single_quoted_keys(self):
        raw = "{'thought': 'test', 'action': 'answer', 'params_update': [], 'question': 'hi'}"
        result = LLMOutput.parse(raw)
        assert result.action == "answer"

    def test_trailing_comma(self):
        raw = '{"thought": "test", "action": "answer", "params_update": [], "question": "hi",}'
        result = LLMOutput.parse(raw)
        assert result.question == "hi"


class TestLLMOutputFallback:
    def test_plain_text_fallback(self):
        raw = "This is just a plain text response without any JSON."
        result = LLMOutput.parse(raw)
        assert result.action == "answer"
        assert result.question == raw
        assert result.params_update == []

    def test_truncated_json_fallback(self):
        raw = '{"thought": "very long thought' + "x" * 5000
        result = LLMOutput.parse(raw)
        assert result.action == "answer"
        assert result.question == raw

    def test_empty_string_fallback(self):
        result = LLMOutput.parse("")
        assert result.action == "answer"
        assert result.question == ""


class TestLLMOutputEdgeCases:
    def test_missing_action_defaults_to_answer(self):
        raw = '{"thought": "test", "params_update": [], "question": "hi"}'
        result = LLMOutput.parse(raw)
        assert result.action == "answer"

    def test_missing_params_update_defaults_to_empty(self):
        raw = '{"thought": "test", "action": "update", "question": "done"}'
        result = LLMOutput.parse(raw)
        assert result.params_update == []

    def test_missing_question_defaults_to_empty(self):
        raw = '{"thought": "test", "action": "answer", "params_update": []}'
        result = LLMOutput.parse(raw)
        assert result.question == ""

    def test_invalid_action_normalized_to_answer(self):
        raw = '{"thought": "test", "action": "INVALID", "params_update": [], "question": "hi"}'
        result = LLMOutput.parse(raw)
        assert result.action == "answer"

    def test_projection_string_value_preserved(self):
        """LLM may output projection as string — should be preserved for UpdateResolver."""
        raw = '{"thought": "test", "action": "update", "params_update": [{"path": "layers.0.projection", "value": "init=epsg:4326"}], "question": "done"}'
        result = LLMOutput.parse(raw)
        assert result.params_update[0]["value"] == "init=epsg:4326"

    def test_status_bool_value_preserved(self):
        """LLM may output status as bool — should be preserved for UpdateResolver."""
        raw = '{"thought": "test", "action": "update", "params_update": [{"path": "layers.0.status", "value": false}], "question": "done"}'
        result = LLMOutput.parse(raw)
        assert result.params_update[0]["value"] is False
