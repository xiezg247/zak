"""LangGraph runner 与适配层测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import StructuredTool

from vnpy_llm.chat.client import StreamCancelled
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.messages import dict_messages_to_langchain
from vnpy_llm.graph.runner import stream_with_tools
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.graph.tools_adapter import openai_tools_to_langchain
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute, IntentCategory


def _config() -> LlmConfig:
    return LlmConfig(
        api_base="https://example.com/v1",
        api_key="test-key",
        model="test-model",
        max_tokens=1024,
        temperature=0.7,
    )


def _graph_ctx(
    user_text: str = "hi",
    category: IntentCategory = "general",
) -> GraphStreamContext:
    return GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category=category)),
        user_text=user_text,
    )


def test_dict_messages_to_langchain_roles():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok"},
        {"role": "tool", "content": "{}", "tool_call_id": "c1"},
    ]
    lc = dict_messages_to_langchain(messages)
    assert [m.type for m in lc] == ["system", "human", "ai", "tool"]


def test_openai_tools_to_langchain_invokes_executor():
    executed: list[tuple[str, dict[str, Any]]] = []

    def executor(name: str, arguments: dict[str, Any]) -> str:
        executed.append((name, arguments))
        return '{"ok": true}'

    specs = [
        {
            "type": "function",
            "function": {
                "name": "get_quote_context",
                "description": "行情",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            },
        }
    ]
    tools = openai_tools_to_langchain(specs, executor)
    assert len(tools) == 1
    assert isinstance(tools[0], StructuredTool)
    assert tools[0].invoke({"symbol": "000001.SZ"}) == '{"ok": true}'
    assert executed == [("get_quote_context", {"symbol": "000001.SZ"})]


class _FakeChatModel(BaseChatModel):
    """可配置响应序列的测试用 ChatModel。"""

    responses: list[AIMessage] = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        message = self.responses.pop(0) if self.responses else AIMessage(content="")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ):
        message = self.responses.pop(0) if self.responses else AIMessage(content="")
        text = message.content if isinstance(message.content, str) else ""
        if text:
            yield ChatGenerationChunk(message=AIMessageChunk(content=text))
        yield ChatGenerationChunk(
            message=AIMessageChunk(content="", tool_calls=message.tool_calls),
        )

    def bind_tools(self, tools: list, **kwargs: Any) -> "_FakeChatModel":
        return self


def test_stream_with_tools_yields_text():
    model = _FakeChatModel()
    model.responses = [AIMessage(content="你好")]

    with patch("vnpy_llm.graph.workflow.create_chat_model", return_value=model):
        deltas = list(
            stream_with_tools(
                _config(),
                [{"role": "user", "content": "hi"}],
                [],
                lambda name, args: "",
                graph_ctx=_graph_ctx(),
            )
        )

    assert deltas == ["你好"]


def test_stream_with_tools_cancel():
    model = _FakeChatModel()
    model.responses = [AIMessage(content="部"), AIMessage(content="分")]

    cancelled = False

    def should_cancel() -> bool:
        return cancelled

    with patch("vnpy_llm.graph.workflow.create_chat_model", return_value=model):
        gen = stream_with_tools(
            _config(),
            [{"role": "user", "content": "hi"}],
            [],
            lambda name, args: "",
            should_cancel=should_cancel,
            graph_ctx=_graph_ctx(),
        )
        assert next(gen) == "部"
        cancelled = True
        try:
            next(gen)
            raise AssertionError("expected StreamCancelled")
        except StreamCancelled:
            pass


def test_stream_with_tools_multi_agent_handoff():
    model = _FakeChatModel()
    model.responses = [
        AIMessage(content="诊断摘要"),
        AIMessage(content="补充大盘情绪"),
    ]
    calls: list[str] = []

    def on_handoff(frm: str, to: str, reason: str) -> None:
        calls.append(f"{frm}->{to}")

    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="diagnosis", confidence="high")),
        user_text="诊断这只，市场冷热如何",
        routing_hint="【路由】diagnosis",
    )

    with patch("vnpy_llm.graph.workflow.create_chat_model", return_value=model):
        deltas = list(
            stream_with_tools(
                _config(),
                [{"role": "user", "content": "诊断这只，市场冷热如何"}],
                [{"type": "function", "function": {"name": "diagnose_stock"}}],
                lambda name, args: "{}",
                graph_ctx=graph_ctx,
                all_tools=[{"type": "function", "function": {"name": "diagnose_stock"}}],
                on_handoff=on_handoff,
            )
        )

    text = "".join(deltas)
    assert "诊断摘要" in text
    assert "补充大盘情绪" in text
    assert "**市场环境**" in text
    assert calls == ["research->market"]
