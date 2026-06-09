"""LLM 结构化意图模型（选股 / 回测等）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentCategory = Literal[
    "general",
    "quote",
    "technical",
    "diagnosis",
    "screening",
    "backtest",
    "watchlist",
    "data",
]

Confidence = Literal["high", "medium", "low"]

BacktestAction = Literal[
    "query_result",
    "list_strategies",
    "list_history",
    "interpret_signals",
    "general",
]


class ScreeningIntent(BaseModel):
    """选股意图结构化字段，供 propose_screening 预填。"""

    intent: str = Field(description="用户原话或归纳后的选股意图")
    preset: str = Field(
        default="",
        description="内置方案：涨幅榜/换手率排行/成交量放大/低 PE/中大盘/主力净流入等",
    )
    top_n: int = Field(default=20, ge=1, le=200)
    scheme_name: str | None = Field(default=None, description="已保存方案名")
    min_change_pct: float | None = None
    max_change_pct: float | None = None
    min_turnover: float | None = None
    confidence: Confidence = "medium"
    clarification_needed: bool = False
    clarifying_questions: list[str] = Field(default_factory=list)


class BacktestIntent(BaseModel):
    """回测相关意图结构化字段。"""

    action: BacktestAction = Field(
        default="general",
        description="query_result=查最近结果; list_strategies=列策略; "
        "list_history=历史对比; interpret_signals=解读策略信号",
    )
    strategy_hint: str = Field(default="", description="用户提到的策略名或关键词")
    history_limit: int = Field(default=10, ge=1, le=50)
    confidence: Confidence = "medium"


class IntentRoute(BaseModel):
    """第一阶段：意图分类。"""

    category: IntentCategory
    confidence: Confidence = "medium"
    reasoning: str = ""


class IntentAnalysis(BaseModel):
    """单次结构化调用：分类 + 可选域内解析。"""

    route: IntentRoute
    screening: ScreeningIntent | None = None
    backtest: BacktestIntent | None = None
