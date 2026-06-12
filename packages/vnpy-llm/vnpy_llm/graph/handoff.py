"""跨 Agent 协作 handoff 规则。

在首 Specialist 完成后串行追加 Agent（通常 research/screening/backtest → market）。
关键词匹配用户原文，不额外调用 LLM。
"""

from __future__ import annotations

from vnpy_llm.graph.state import AgentName
from vnpy_llm.routing.intent import IntentCategory

# 综合诊断 + 大盘/情绪 → 追加 market
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

# 回测解读 + 技术形态 → 追加 market
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

# 选股 + 技术面扫描 → 追加 market
_SCREENING_MARKET_KEYWORDS = (
    "技术面",
    "技术扫描",
    "技术面对比",
    "均线情况",
)

_HANDOFF_RULES: tuple[tuple[IntentCategory, tuple[str, ...], str, str], ...] = (
    ("diagnosis", _RESEARCH_MARKET_KEYWORDS, "market", "用户需要综合诊断并结合大盘/市场情绪"),
    ("backtest", _BACKTEST_MARKET_KEYWORDS, "market", "用户需要回测解读并结合技术形态/策略信号"),
    ("screening", _SCREENING_MARKET_KEYWORDS, "market", "用户需要选股结果并结合技术面扫描"),
)


def resolve_handoff_agents(
    category: IntentCategory,
    user_text: str,
) -> tuple[list[AgentName], str]:
    """根据意图类别与用户原文决定是否 handoff。"""
    text = user_text.strip()
    if not text:
        return [], ""

    for rule_category, keywords, agent, reason in _HANDOFF_RULES:
        if category == rule_category and _contains_any(text, keywords):
            return [agent], reason
    return [], ""


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(keyword in text or keyword.lower() in lower for keyword in keywords)
