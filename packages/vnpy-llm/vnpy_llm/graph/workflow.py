"""LangGraph Agent 图构建（langchain.agents.create_agent）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.llm import create_chat_model
from vnpy_llm.graph.tools_adapter import openai_tools_to_langchain


def build_agent_graph(
    config: LlmConfig,
    openai_tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
) -> CompiledStateGraph:
    """构建单段 ReAct 图：ChatOpenAI + StructuredTool 列表。

    system prompt 由 runner 写入 messages[0]，此处不重复绑定。
    """
    llm = create_chat_model(config)
    tools = openai_tools_to_langchain(openai_tools, tool_executor)
    return create_agent(llm, tools)


# 兼容旧名
build_react_agent = build_agent_graph
