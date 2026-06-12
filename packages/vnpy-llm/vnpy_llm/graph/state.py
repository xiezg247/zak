"""LangGraph 编排状态与 Supervisor 决策模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from vnpy_llm.routing.intent import (
    BacktestIntent,
    IntentAnalysis,
    IntentCategory,
    IntentRoute,
    ScreeningIntent,
)

AgentName = Literal["market", "research", "screening", "backtest", "data", "general"]

CATEGORY_TO_AGENT: dict[IntentCategory, AgentName] = {
    "quote": "market",
    "technical": "market",
    "diagnosis": "research",
    "screening": "screening",
    "backtest": "backtest",
    "watchlist": "market",
    "data": "data",
    "general": "general",
}

AGENT_TOOL_CATEGORIES: dict[AgentName, frozenset[IntentCategory]] = {
    "market": frozenset({"quote", "technical", "watchlist"}),
    "research": frozenset({"diagnosis"}),
    "screening": frozenset({"screening"}),
    "backtest": frozenset({"backtest"}),
    "data": frozenset({"data"}),
    "general": frozenset(),
}

MAX_HANDOFFS = 2

AGENT_STREAM_LABELS: dict[AgentName, str] = {
    "market": "市场环境",
    "research": "个股研究",
    "screening": "选股方案",
    "backtest": "回测解读",
    "data": "数据查询",
    "general": "",
}


class SupervisorDecision(BaseModel):
    """Supervisor 委派结果（由意图路由 + handoff 规则生成）。"""

    target_agent: AgentName
    route: IntentRoute
    screening: ScreeningIntent | None = None
    backtest: BacktestIntent | None = None
    handoff_agents: list[AgentName] = Field(default_factory=list)
    handoff_reason: str = ""


class GraphStreamContext(BaseModel):
    """Runner 构建各 Agent system prompt 所需的共享上下文。"""

    analysis: IntentAnalysis
    user_text: str
    routing_hint: str = ""
    tools_summary: str = ""
    skills_text: str = ""
    mcp_text: str = ""
    context_text: str = ""
    page_prompt: str = ""
    strategy_prompt: str = ""

    model_config = {"arbitrary_types_allowed": True}
