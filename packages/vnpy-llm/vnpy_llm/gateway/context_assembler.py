"""上下文与 System Prompt 单一组装点（Gateway 控制面子模块）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vnpy_common.ai.access import get_ai_context
from vnpy_llm.chat.store import MAX_TOOL_RESULT_CHARS, ChatMessage
from vnpy_llm.gateway.tool_registry import ToolRegistry
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.routing.prompts import (
    SYSTEM_PROMPT,
    build_page_prompt,
    build_strategy_prompt,
)


class ContextAssembler:
    """拼装终端上下文、工具摘要与 API / Graph 消息。"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        *,
        extra_context_provider: Callable[[], str] | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._extra_context_provider = extra_context_provider

    def set_extra_context_provider(self, provider: Callable[[], str] | None) -> None:
        self._extra_context_provider = provider

    def get_context_text(self) -> str:
        parts: list[str] = []
        ctx = get_ai_context()
        context_text = ctx.to_text()
        if context_text:
            parts.append(context_text)
        if self._extra_context_provider:
            extra = self._extra_context_provider().strip()
            if extra:
                parts.append(extra)
        return "\n".join(parts)

    def build_tools_summary(self) -> str:
        """生成可用工具能力摘要。"""
        capabilities: list[str] = []
        for name in self._tool_registry.skill_engine.skill_names():
            if name.startswith("vnpy-data"):
                capabilities.append("数据查询(K线/行情)")
            elif name.startswith("vnpy-backtest"):
                capabilities.append("策略回测")
            elif name.startswith("vnpy-screening"):
                capabilities.append("选股筛选")
            elif name.startswith("vnpy-radar"):
                capabilities.append("雷达盘面/龙头选股")
            elif name.startswith("vnpy-analysis"):
                capabilities.append("技术形态/策略信号")
            elif name.startswith("tdx-financial-analysis"):
                capabilities.append("财务深度分析(团队)")
            elif name.startswith("tdx-risk-analysis"):
                capabilities.append("风险分析(团队)")
            elif name.startswith("tdx-stock-diagnose"):
                capabilities.append("个股诊断(通达信)")
            elif name.startswith("vnpy-watchlist"):
                capabilities.append("自选管理")
            elif name.startswith("vnpy-notes"):
                capabilities.append("个股笔记")
            elif name.startswith("vnpy-feed"):
                capabilities.append("B站信息流订阅")
            elif name.startswith("vnpy-sentiment"):
                capabilities.append("全市场恐贪指数")
        if capabilities:
            return "\n".join(
                [
                    "【可用工具能力】",
                    "你拥有以下工具能力，涉及行情、K线、财务数据时必须调用工具获取真实数据，禁止编造。",
                    "  " + "、".join(sorted(set(capabilities))),
                ]
            )
        return ""

    @staticmethod
    def chat_message_to_dict(item: ChatMessage) -> dict[str, str]:
        """单条会话消息转 API dict；tool 结果过长时截断以控制 token。"""
        content = item.content
        if item.role == "tool" and len(content) > MAX_TOOL_RESULT_CHARS:
            content = content[:MAX_TOOL_RESULT_CHARS] + "\n...(结果过长已截断)"
        return {"role": item.role, "content": content}

    def build_conversation_messages(self, messages: list[ChatMessage]) -> list[dict[str, str]]:
        """LangGraph 路径：仅 user/assistant/tool 历史，system 由 graph/agents 拼装。"""
        return [self.chat_message_to_dict(item) for item in messages]

    def build_api_messages(
        self,
        messages: list[ChatMessage],
        *,
        extra_system: str = "",
    ) -> list[dict[str, str]]:
        system_parts = [SYSTEM_PROMPT]
        tools_summary = self.build_tools_summary()
        if tools_summary:
            system_parts.append(tools_summary)
        skills_text = self._tool_registry.skill_engine.build_skills_prompt()
        if skills_text:
            system_parts.append(skills_text)
        strategy_prompt = build_strategy_prompt()
        if strategy_prompt:
            system_parts.append(strategy_prompt)
        mcp_text = self._tool_registry.mcp_engine.build_internal_status_note()
        if mcp_text:
            system_parts.append(mcp_text)
        context_text = self.get_context_text()
        if context_text:
            system_parts.append("\n【当前终端上下文】\n" + context_text)
        page_prompt = build_page_prompt(get_ai_context().page)
        if page_prompt:
            system_parts.append(page_prompt)
        if extra_system.strip():
            system_parts.append(extra_system.strip())
        api_messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(system_parts)}]
        api_messages.extend(self.chat_message_to_dict(item) for item in messages)
        return api_messages

    def build_graph_stream_context(self, route_ctx: Any, user_text: str) -> GraphStreamContext:
        page = get_ai_context().page
        return GraphStreamContext(
            analysis=route_ctx.analysis,
            user_text=user_text,
            routing_hint=route_ctx.routing_hint,
            tools_summary=self.build_tools_summary(),
            skills_text=self._tool_registry.skill_engine.build_skills_prompt(),
            mcp_text=self._tool_registry.mcp_engine.build_internal_status_note(),
            context_text=self.get_context_text(),
            page_prompt=build_page_prompt(page),
            strategy_prompt=build_strategy_prompt(),
        )
