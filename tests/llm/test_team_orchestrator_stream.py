"""投研团队 orchestrator 流式输出测试。"""

from __future__ import annotations

import queue
import time
from unittest.mock import MagicMock

import pytest

from vnpy_llm.chat.client import StreamCancelled
from vnpy_llm.graph.orchestrator import (
    AgentStreamEvent,
    AgentTaskSpec,
    _run_single_agent_streaming,
)
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute


def test_run_single_agent_streaming_emits_deltas_before_done(monkeypatch):
    """worker 应在 done 之前将 token delta 推入队列。"""
    emitted: list[str] = []

    def fake_stream_agent(config, messages, tools, tool_executor, **kwargs):
        for ch in ("财", "务", "面"):
            time.sleep(0.005)
            yield ch

    monkeypatch.setattr("vnpy_llm.graph.orchestrator._stream_agent", fake_stream_agent)

    event_queue: queue.Queue = queue.Queue()
    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="team_analysis")),
        user_text="/team 600519",
    )
    task = AgentTaskSpec(
        user_msg={"role": "user", "content": "分析"},
        use_tools=False,
        max_rounds=1,
    )

    _run_single_agent_streaming(
        "financial",
        [],
        task,
        [],
        MagicMock(),
        MagicMock(configured=True),
        graph_ctx,
        None,
        event_queue,
    )

    kinds: list[str] = []
    while not event_queue.empty():
        event: AgentStreamEvent = event_queue.get_nowait()
        kinds.append(event.kind)
        if event.kind == "delta":
            emitted.append(event.text)

    assert kinds[:3] == ["delta", "delta", "delta"]
    assert kinds[-1] == "done"
    assert "".join(emitted) == "财务面"


def test_run_single_agent_streaming_propagates_cancel(monkeypatch):
    def fake_stream_agent(config, messages, tools, tool_executor, **kwargs):
        yield "x"
        if kwargs.get("should_cancel") and kwargs["should_cancel"]():
            from vnpy_llm.chat.client import StreamCancelled

            raise StreamCancelled("cancel")

    monkeypatch.setattr("vnpy_llm.graph.orchestrator._stream_agent", fake_stream_agent)

    event_queue: queue.Queue = queue.Queue()
    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="team_analysis")),
        user_text="/team 600519",
    )
    task = AgentTaskSpec(user_msg={"role": "user", "content": "x"}, use_tools=False, max_rounds=1)

    with pytest.raises(StreamCancelled):
        _run_single_agent_streaming(
            "financial",
            [],
            task,
            [],
            MagicMock(),
            MagicMock(configured=True),
            graph_ctx,
            lambda: True,
            event_queue,
        )

    events = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())
    assert any(e.kind == "error" for e in events)
