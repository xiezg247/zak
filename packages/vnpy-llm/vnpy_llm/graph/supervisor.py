"""Supervisor：意图路由 → Agent 委派 + handoff。"""

from __future__ import annotations

from typing import Any

from vnpy_llm.graph.handoff import resolve_handoff_agents
from vnpy_llm.graph.state import (
    AGENT_TOOL_CATEGORIES,
    CATEGORY_TO_AGENT,
    AgentName,
    SupervisorDecision,
)
from vnpy_llm.routing.intent import IntentAnalysis
from vnpy_llm.routing.router import (
    AGENT_TOOL_NAMES,
    FEAR_GREED_TOOL,
    TOOL_GROUPS,
    apply_fear_greed_tools,
    filter_tools_by_route,
)


def resolve_target_agent(analysis: IntentAnalysis) -> AgentName:
    """将 IntentCategory 映射为 Specialist Agent。"""
    return CATEGORY_TO_AGENT.get(analysis.route.category, "general")


def build_supervisor_decision(
    analysis: IntentAnalysis,
    user_text: str,
) -> SupervisorDecision:
    """由现有 IntentAnalysis 生成 Supervisor 委派决策。"""
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


def filter_tools_for_agent(
    agent: AgentName,
    all_tools: list[dict[str, Any]],
    *,
    analysis: IntentAnalysis | None = None,
    user_text: str = "",
    mcp_tool_names: frozenset[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """按 Specialist Agent 合并其域内 TOOL_GROUPS 并过滤。"""
    if not all_tools:
        return []
    if agent == "general":
        return []

    allowed: set[str] = set()
    for category in AGENT_TOOL_CATEGORIES.get(agent, frozenset()):
        allowed |= set(TOOL_GROUPS.get(category, frozenset()))

    if agent == "data":
        allowed |= set(AGENT_TOOL_NAMES)
        if mcp_tool_names:
            allowed |= set(mcp_tool_names)

    if not allowed:
        return list(all_tools)

    filtered = [
        tool
        for tool in all_tools
        if (tool.get("function") or {}).get("name", "") in allowed
    ]
    result = filtered if filtered else list(all_tools)

    if analysis is not None and agent == "market":
        result = apply_fear_greed_tools(result, analysis, all_tools)
        from vnpy_llm.routing.router import _is_trend_scenario_request

        if _is_trend_scenario_request(user_text):
            result = [tool for tool in result if (tool.get("function") or {}).get("name", "") != FEAR_GREED_TOOL]
    return result
