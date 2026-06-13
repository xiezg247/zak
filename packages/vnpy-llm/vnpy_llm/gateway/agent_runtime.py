"""Agent 流式运行时：有工具 / 无工具统一入口。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from vnpy_llm.chat.client import stream_chat_completion
from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.runner import stream_with_tools
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.routing.router import RouteContext


class AgentRuntime:
    """封装 LangGraph 工具链与纯文本聊天两条流式路径。"""

    @staticmethod
    def stream_deltas(
        config: LlmConfig,
        *,
        all_tools: list[dict[str, Any]],
        conversation_messages: list[dict[str, str]],
        api_messages: list[dict[str, str]],
        route_ctx: RouteContext | None,
        graph_ctx: GraphStreamContext | None,
        mcp_tool_names: frozenset[str],
        tool_executor: Callable[[str, dict[str, Any]], str],
        should_cancel: Callable[[], bool] | None = None,
        on_handoff: Callable[[str, str, str], None] | None = None,
    ) -> Iterator[str]:
        """按工具可用性选择 agent 或 chat 路径，统一 yield 文本 delta。"""
        if all_tools and route_ctx is not None and graph_ctx is not None:
            yield from stream_with_tools(
                config,
                conversation_messages,
                route_ctx.tools,
                tool_executor,
                should_cancel=should_cancel,
                graph_ctx=graph_ctx,
                all_tools=all_tools,
                mcp_tool_names=mcp_tool_names,
                on_handoff=on_handoff,
            )
            return
        yield from stream_chat_completion(
            config,
            api_messages,
            should_cancel=should_cancel,
        )
