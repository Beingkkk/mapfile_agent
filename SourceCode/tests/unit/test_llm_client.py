"""Tests for LLMClient.

DC-019  plan-backend-llm §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_BACKEND_LLM = Path(__file__).resolve().parent.parent.parent / "backend" / "llm"
if str(_BACKEND_LLM) not in sys.path:
    sys.path.insert(0, str(_BACKEND_LLM))

import pytest

from llm_client import LLMClient


class MockMessage:
    def __init__(self, text: str):
        self.content = [MagicMock(type="text", text=text)]


class MockUsage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class TestLLMClientInit:
    def test_default_params(self):
        client = LLMClient(api_key="test-key")
        assert client._model == "claude-3-sonnet-20240229"
        assert client._temperature == 0.1
        assert client._max_retries == 3

    def test_custom_params(self):
        client = LLMClient(
            api_key="test-key",
            model="claude-3-opus",
            base_url="https://custom.api",
            temperature=0.5,
            max_retries=5,
        )
        assert client._model == "claude-3-opus"
        assert client._base_url == "https://custom.api"
        assert client._temperature == 0.5
        assert client._max_retries == 5


class TestLLMClientChat:
    @patch("llm_client.anthropic.Anthropic")
    def test_chat_returns_content(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text='{"action": "answer"}')]
        mock_response.usage = MockUsage()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")
        result = client.chat("Hello, LLM")

        assert result == '{"action": "answer"}'
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]
        assert call_args["model"] == "claude-3-sonnet-20240229"
        assert call_args["temperature"] == 0.1
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Hello, LLM"

    @patch("llm_client.anthropic.Anthropic")
    def test_chat_records_usage(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="hi")]
        mock_response.usage = MockUsage(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")
        client.chat("test")

        assert client.last_usage == {"input_tokens": 100, "output_tokens": 50}

    @patch("llm_client.anthropic.Anthropic")
    def test_chat_retry_on_error(self, mock_anthropic_class):
        mock_client = MagicMock()
        # First two calls fail, third succeeds
        mock_client.messages.create.side_effect = [
            Exception("API Error"),
            Exception("API Error"),
            MagicMock(
                content=[MagicMock(type="text", text="success")],
                usage=MockUsage(),
            ),
        ]
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key", max_retries=3)
        result = client.chat("test")

        assert result == "success"
        assert mock_client.messages.create.call_count == 3

    @patch("llm_client.anthropic.Anthropic")
    def test_chat_retry_exhausted_raises(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Persistent error")
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key", max_retries=2)
        with pytest.raises(Exception, match="Persistent error"):
            client.chat("test")

        assert mock_client.messages.create.call_count == 2

    @patch("llm_client.anthropic.Anthropic")
    def test_chat_max_tokens_set(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="ok")]
        mock_response.usage = MockUsage()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")
        client.chat("test")

        call_args = mock_client.messages.create.call_args[1]
        assert "max_tokens" in call_args
        assert call_args["max_tokens"] == 4096

    @patch("llm_client.anthropic.Anthropic")
    def test_chat_system_prompt_set(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="ok")]
        mock_response.usage = MockUsage()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")
        client.chat("test")

        call_args = mock_client.messages.create.call_args[1]
        assert call_args.get("system") == "You are a MapServer configuration assistant."
