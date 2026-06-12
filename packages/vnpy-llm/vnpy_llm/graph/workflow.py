"""LangGraph ReAct Agent 图构建。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from vnpy_llm.config.settings import LlmConfig
from vnpy_llm.graph.llm import create_chat_model
from vnpy_llm.graph.tools_adapter import openai_tools_to_langchain


def build_react_agent(
    config: LlmConfig,
    openai_tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], str],
) -> CompiledStateGraph:
    """构建单 Agent ReAct 图（Phase 1）。"""
    llm = create_chat_model(config)
    tools = openai_tools_to_langchain(openai_tools, tool_executor)
    return create_agent(llm, tools)
