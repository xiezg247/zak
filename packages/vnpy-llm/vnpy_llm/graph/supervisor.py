"""Supervisor：意图路由 → Agent 委派 + 工具域过滤。

与 routing/router.py 分工：
- router：LLM/规则做意图分类，产出 route_ctx.tools 与 routing_hint
- supervisor：把 category 映射到 Specialist Agent，并按 Agent 合并 TOOL_GROUPS
"""

from __future__ import annotations

from typing import Any

from vnpy_llm.graph.handoff import resolve_handoff_agents
from vnpy_llm.graph.state import (
    AGENT_TOOL_CATEGORIES,
    CATEGORY_TO_AGENT,
    AgentName,
    SupervisorDecision,
)
from vnpy_llm.graph.tool_utils import filter_openai_tools
from vnpy_llm.routing.intent import IntentAnalysis
from vnpy_llm.routing.router import (
    AGENT_TOOL_NAMES,
    FEAR_GREED_TOOL,
    TOOL_GROUPS,
    _is_trend_scenario_request,
    apply_fear_greed_tools,
)


def resolve_target_agent(analysis: IntentAnalysis) -> AgentName:
    """IntentCategory → Specialist Agent（见 state.CATEGORY_TO_AGENT）。"""
    return CATEGORY_TO_AGENT.get(analysis.route.category, "general")


def build_supervisor_decision(
    analysis: IntentAnalysis,
    user_text: str,
) -> SupervisorDecision:
    """由 IntentAnalysis 生成委派决策；handoff 至多追加 1 个 Agent（与 MAX_HANDOFFS 对齐）。"""
    target = resolve_target_agent(analysis)
    handoff_agents, handoff_reason = resolve_handoff_agents(analysis.route.category, user_text)
    handoff_agents = [agent for agent in handoff_agents if agent != target][:1]
    return SupervisorDecision(
        target_agent=target,
        route=analysis.route,
        screening=analysis.screening,
        backtest=analysis.backtest,
        handoff_agents=handoff_agents,
        handoff_reason=handoff_reason,
    )


def _allowed_tool_names_for_agent(
    agent: AgentName,
    *,
    mcp_tool_names: frozenset[str] | set[str] | None,
) -> set[str]:
    """合并 Agent 负责的全部 IntentCategory 对应工具名。"""
    if agent == "general":
        return set()

    allowed: set[str] = set()
    for category in AGENT_TOOL_CATEGORIES.get(agent, frozenset()):
        allowed |= set(TOOL_GROUPS.get(category, frozenset()))

    if agent == "data":
        allowed |= set(AGENT_TOOL_NAMES)
        if mcp_tool_names:
            allowed |= set(mcp_tool_names)
    return allowed


def filter_tools_for_agent(
    agent: AgentName,
    all_tools: list[dict[str, Any]],
    *,
    analysis: IntentAnalysis | None = None,
    user_text: str = "",
    mcp_tool_names: frozenset[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """按 Specialist Agent 过滤 OpenAI tools 列表。"""
    if not all_tools:
        return []
    if agent == "general":
        return []

    allowed = _allowed_tool_names_for_agent(agent, mcp_tool_names=mcp_tool_names)
    if not allowed:
        return list(all_tools)

    result = filter_openai_tools(all_tools, allowed=allowed)
    if not result:
        return list(all_tools)

    if analysis is not None and agent == "market":
        result = apply_fear_greed_tools(result, analysis, all_tools)
        if _is_trend_scenario_request(user_text):
            result = filter_openai_tools(result, blocked={FEAR_GREED_TOOL})
    return result
