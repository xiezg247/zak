"""跨 Agent 协作 handoff 规则。"""

from __future__ import annotations

from vnpy_llm.graph.state import AgentName
from vnpy_llm.routing.intent import IntentCategory

_RESEARCH_MARKET_KEYWORDS = (
    "大盘",
    "市场情绪",
    "市场怎么样",
    "大盘怎么样",
    "市场冷热",
    "恐贪",
    "贪婪",
    "恐慌",
    "赚钱效应",
    "过热",
    "冰点",
    "择时",
    "市场环境",
)

_BACKTEST_MARKET_KEYWORDS = (
    "均线",
    "技术形态",
    "技术面",
    "金叉",
    "死叉",
    "信号",
    "MA",
    "形态",
)

_SCREENING_MARKET_KEYWORDS = (
    "技术面",
    "技术扫描",
    "技术面对比",
    "均线情况",
)


def resolve_handoff_agents(
    category: IntentCategory,
    user_text: str,
) -> tuple[list[AgentName], str]:
    """根据意图类别与用户原文决定是否 handoff 至其他 Agent。"""
    text = user_text.strip()
    if not text:
        return [], ""

    if category == "diagnosis" and _contains_any(text, _RESEARCH_MARKET_KEYWORDS):
        return ["market"], "用户需要综合诊断并结合大盘/市场情绪"

    if category == "backtest" and _contains_any(text, _BACKTEST_MARKET_KEYWORDS):
        return ["market"], "用户需要回测解读并结合技术形态/策略信号"

    if category == "screening" and _contains_any(text, _SCREENING_MARKET_KEYWORDS):
        return ["market"], "用户需要选股结果并结合技术面扫描"

    return [], ""


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(keyword in text or keyword.lower() in lower for keyword in keywords)
