"""意图路由单元测试。"""

from __future__ import annotations

from vnpy_llm.intent import BacktestIntent, IntentAnalysis, IntentRoute, MarketEnrichment, ScreeningIntent
from vnpy_llm.routing import (
    FEAR_GREED_TOOL,
    apply_fear_greed_tools,
    build_routing_hint,
    filter_tools_by_route,
    _keyword_fallback,
    _normalize_market_enrichment,
)


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "description": name}}


ALL_TOOLS = [
    _tool("get_quote_context"),
    _tool("screen_by_condition"),
    _tool("screen_by_pattern"),
    _tool("propose_screening"),
    _tool("list_screeners"),
    _tool("get_backtest_result"),
    _tool("diagnose_stock"),
    _tool("read_skill_file"),
    _tool("mcp_tdx_wenda"),
]


def test_filter_screening_subset():
    filtered = filter_tools_by_route(ALL_TOOLS, "screening")
    names = {t["function"]["name"] for t in filtered}
    assert "screen_by_condition" in names
    assert "screen_by_pattern" in names
    assert "propose_screening" in names
    assert "list_screeners" in names
    assert "read_skill_file" in names
    assert "get_backtest_result" not in names


def test_filter_diagnosis_includes_mcp():
    filtered = filter_tools_by_route(
        ALL_TOOLS,
        "diagnosis",
        mcp_tool_names={"mcp_tdx_wenda"},
    )
    names = {t["function"]["name"] for t in filtered}
    assert "diagnose_stock" in names
    assert "mcp_tdx_wenda" in names


def test_filter_general_returns_all():
    assert filter_tools_by_route(ALL_TOOLS, "general") == ALL_TOOLS


def test_keyword_fallback_screening():
    result = _keyword_fallback("帮我选今天涨最多的", "")
    assert result is not None
    assert result.route.category == "screening"
    assert result.screening is not None
    assert result.screening.intent


def test_build_routing_hint_screening():
    analysis = IntentAnalysis(
        route=IntentRoute(category="screening", confidence="high", reasoning="用户要选股"),
        screening=ScreeningIntent(
            intent="涨幅榜前20",
            preset="涨幅榜",
            top_n=20,
            confidence="high",
        ),
    )
    hint = build_routing_hint(analysis, page="选股")
    assert "screen_by_condition" in hint
    assert "涨幅榜" in hint
    assert "选股" in hint


def test_build_routing_hint_screening_medium():
    analysis = IntentAnalysis(
        route=IntentRoute(category="screening", confidence="medium", reasoning="用户要选股"),
        screening=ScreeningIntent(
            intent="找一些低估值的",
            preset="",
            top_n=20,
            confidence="medium",
        ),
    )
    hint = build_routing_hint(analysis, page="选股")
    assert "propose_screening" in hint
    assert "可直接调用 screen_by_condition" not in hint


def test_build_routing_hint_backtest():
    analysis = IntentAnalysis(
        route=IntentRoute(category="backtest", confidence="medium"),
        backtest=BacktestIntent(action="list_history", history_limit=5),
    )
    hint = build_routing_hint(analysis)
    assert "list_backtest_history" in hint
    assert "list_history" in hint
    assert "恐贪指数" in hint


def test_build_routing_hint_market_consider():
    analysis = IntentAnalysis(
        route=IntentRoute(category="diagnosis", confidence="medium"),
    )
    analysis = _normalize_market_enrichment(analysis, "这只票怎么样", "")
    hint = build_routing_hint(analysis)
    assert "consider" in hint or "可自行判断" in hint


def test_apply_fear_greed_on_filtered_tools():
    tools = filter_tools_by_route(ALL_TOOLS, "quote")
    analysis = IntentAnalysis(
        route=IntentRoute(category="quote", confidence="medium"),
        market=MarketEnrichment(fear_greed="consider"),
    )
    all_tools = ALL_TOOLS + [_tool(FEAR_GREED_TOOL)]
    enriched = apply_fear_greed_tools(tools, analysis, all_tools)
    names = {item["function"]["name"] for item in enriched}
    assert FEAR_GREED_TOOL in names
