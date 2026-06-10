"""LLM 客户端工具调用测试。"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from vnpy_llm.chat.client import (
    _execute_tool_calls_parallel,
    complete_with_tools,
    stream_with_tools,
)
from vnpy_llm.config.settings import LlmConfig


def _config() -> LlmConfig:
    return LlmConfig(
        api_base="https://example.com/v1",
        api_key="test-key",
        model="test-model",
        max_tokens=1024,
        temperature=0.7,
    )


def _make_call(name: str, arguments: str = "{}", call_id: str = "call_1"):
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    call = MagicMock()
    call.id = call_id
    call.type = "function"
    call.function = fn
    return call


def test_parallel_tool_execution():
    order: list[str] = []

    def executor(name: str, arguments: dict) -> str:
        if name == "slow_a":
            time.sleep(0.05)
        order.append(name)
        return f"ok:{name}"

    calls = [_make_call("slow_a", call_id="1"), _make_call("fast_b", call_id="2")]
    pairs = _execute_tool_calls_parallel(calls, executor)
    assert [call.function.name for call, _ in pairs] == ["slow_a", "fast_b"]
    assert order == ["fast_b", "slow_a"] or len(order) == 2


def test_complete_with_tools_parallel_round():
    config = _config()

    tool_message = MagicMock()
    tool_message.content = None
    tool_message.tool_calls = [
        _make_call("tool_a", call_id="1"),
        _make_call("tool_b", call_id="2"),
    ]

    final_message = MagicMock()
    final_message.content = "完成"
    final_message.tool_calls = []

    response_tools = MagicMock()
    response_tools.choices = [MagicMock(message=tool_message)]

    response_final = MagicMock()
    response_final.choices = [MagicMock(message=final_message)]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [response_tools, response_final]

    executed: list[str] = []

    def executor(name: str, arguments: dict) -> str:
        executed.append(name)
        return json.dumps({"tool": name})

    with patch("vnpy_llm.chat.client.create_openai_client", return_value=mock_client):
        content, messages = complete_with_tools(
            config,
            [{"role": "user", "content": "hi"}],
            [{"type": "function", "function": {"name": "tool_a"}}],
            executor,
        )

    assert content == "完成"
    assert set(executed) == {"tool_a", "tool_b"}
    assert mock_client.chat.completions.create.call_count == 2


def test_stream_with_tools_yields_deltas():
    config = _config()

    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].finish_reason = "stop"
    chunk.choices[0].delta = MagicMock(content="你好", tool_calls=None)

    mock_stream = iter([chunk])
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_stream

    with patch("vnpy_llm.chat.client.create_openai_client", return_value=mock_client):
        deltas = list(
            stream_with_tools(
                config,
                [{"role": "user", "content": "hi"}],
                [],
                lambda name, args: "",
            )
        )

    assert deltas == ["你好"]
