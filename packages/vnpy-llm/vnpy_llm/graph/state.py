"""LangGraph 编排状态与 Supervisor 决策模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from vnpy_common.domain.base import FrozenModel, MutableModel
from vnpy_llm.routing.intent import (
    BacktestIntent,
    IntentAnalysis,
    IntentCategory,
    IntentRoute,
    ScreeningIntent,
)

AgentName = Literal["market", "research", "screening", "backtest", "data", "general", "financial", "risk", "strategy", "chief"]

# 意图类别 → 默认 Specialist（handoff 可再追加 market 等）
CATEGORY_TO_AGENT: dict[IntentCategory, AgentName] = {
    "quote": "market",
    "technical": "market",
    "market": "market",
    "diagnosis": "research",
    "screening": "screening",
    "backtest": "backtest",
    "watchlist": "market",
    "data": "data",
    "general": "general",
    "team_analysis": "chief",
}

# 各 Agent 可合并的 TOOL_GROUPS 类别（general 无工具）
AGENT_TOOL_CATEGORIES: dict[AgentName, frozenset[IntentCategory]] = {
    "market": frozenset({"quote", "technical", "watchlist", "market"}),
    "research": frozenset({"diagnosis"}),
    "screening": frozenset({"screening"}),
    "backtest": frozenset({"backtest"}),
    "data": frozenset({"data"}),
    "general": frozenset(),
    "financial": frozenset({"team_analysis"}),
    "risk": frozenset({"team_analysis"}),
    "strategy": frozenset({"team_analysis"}),
    "chief": frozenset({"team_analysis"}),
}

# handoff 串行上限（含首 Agent）
MAX_HANDOFFS = 2

# 多 Agent 流式输出时段标题（Markdown）
AGENT_STREAM_LABELS: dict[AgentName, str] = {
    "market": "市场环境",
    "research": "个股研究",
    "screening": "选股方案",
    "backtest": "回测解读",
    "data": "数据查询",
    "general": "",
    "financial": "财务面",
    "risk": "风险面",
    "strategy": "策略面",
    "chief": "综合研判",
}


class SupervisorDecision(FrozenModel):
    """Supervisor 委派结果（意图路由 + handoff 规则）。"""

    target_agent: AgentName
    route: IntentRoute
    screening: ScreeningIntent | None = None
    backtest: BacktestIntent | None = None
    handoff_agents: list[AgentName] = Field(default_factory=list)
    handoff_reason: str = ""


class GraphStreamContext(MutableModel):
    """Runner 拼装各 Agent system prompt 的共享上下文（每轮用户消息构建一次）。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    analysis: IntentAnalysis
    user_text: str
    routing_hint: str = ""
    tools_summary: str = ""
    skills_text: str = ""
    mcp_text: str = ""
    context_text: str = ""
    page_prompt: str = ""
    strategy_prompt: str = ""
    team_prefetch: dict[str, Any] | None = None
    team_scores: dict[str, Any] | None = None
    market_prefetch: dict[str, Any] | None = None
