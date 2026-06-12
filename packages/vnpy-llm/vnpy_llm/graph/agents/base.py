"""各 Agent 共享的 system prompt 基座与拼装。"""

from __future__ import annotations

from vnpy_llm.graph.state import AgentName, GraphStreamContext
from vnpy_llm.routing.base_prompt import BASE_PROMPT

_AGENT_DOMAIN_GETTERS: dict[AgentName, str] = {}


def register_agent_prompt(agent: AgentName, prompt: str) -> None:
    _AGENT_DOMAIN_GETTERS[agent] = prompt


def get_agent_domain_prompt(agent: AgentName) -> str:
    return _AGENT_DOMAIN_GETTERS.get(agent, "")


def build_agent_system_prompt(
    agent: AgentName,
    ctx: GraphStreamContext,
    *,
    handoff_context: str = "",
) -> str:
    """拼装 Specialist Agent 的 system prompt。"""
    parts = [BASE_PROMPT, f"【当前 Agent】{agent}"]
    domain = get_agent_domain_prompt(agent)
    if domain:
        parts.append(domain)
    if agent == "backtest" and ctx.strategy_prompt.strip():
        parts.append(ctx.strategy_prompt.strip())
    if ctx.tools_summary.strip():
        parts.append(ctx.tools_summary.strip())
    if ctx.skills_text.strip():
        parts.append(ctx.skills_text.strip())
    if ctx.mcp_text.strip():
        parts.append(ctx.mcp_text.strip())
    if ctx.context_text.strip():
        parts.append("\n【当前终端上下文】\n" + ctx.context_text.strip())
    if ctx.page_prompt.strip():
        parts.append(ctx.page_prompt.strip())
    if ctx.routing_hint.strip():
        parts.append(ctx.routing_hint.strip())
    if handoff_context.strip():
        parts.append("\n【协作续接】\n" + handoff_context.strip())
    return "\n".join(parts)
