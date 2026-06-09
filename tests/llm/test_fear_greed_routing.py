"""恐贪 enrichment 路由测试。"""

from __future__ import annotations

from vnpy_llm.intent import IntentAnalysis, IntentRoute, MarketEnrichment
from vnpy_llm.routing import FEAR_GREED_TOOL, _normalize_market_enrichment, apply_fear_greed_tools


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name}}


def test_apply_fear_greed_skip():
    all_tools = [_tool("get_quote_context"), _tool(FEAR_GREED_TOOL)]
    analysis = IntentAnalysis(
        route=IntentRoute(category="quote", confidence="medium"),
        market=MarketEnrichment(fear_greed="skip"),
    )
    filtered = apply_fear_greed_tools(all_tools, analysis, all_tools)
    names = {item["function"]["name"] for item in filtered}
    assert FEAR_GREED_TOOL not in names


def test_apply_fear_greed_consider_adds_tool():
    all_tools = [_tool("diagnose_stock"), _tool(FEAR_GREED_TOOL)]
    tools = [_tool("diagnose_stock")]
    analysis = IntentAnalysis(
        route=IntentRoute(category="diagnosis", confidence="medium"),
        market=MarketEnrichment(fear_greed="consider"),
    )
    filtered = apply_fear_greed_tools(tools, analysis, all_tools)
    names = {item["function"]["name"] for item in filtered}
    assert FEAR_GREED_TOOL in names


def test_normalize_market_enrichment_highlight():
    analysis = IntentAnalysis(route=IntentRoute(category="general", confidence="medium"))
    normalized = _normalize_market_enrichment(analysis, "现在市场是不是太贪婪了", "")
    assert normalized.market.fear_greed == "highlight"
