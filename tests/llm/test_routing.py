"""意图路由单元测试。"""

from __future__ import annotations

from vnpy_llm.routing.intent import BacktestIntent, IntentAnalysis, IntentRoute, MarketEnrichment, ScreeningIntent
from vnpy_llm.routing.router import (
    FEAR_GREED_TOOL,
    _keyword_fallback,
    _normalize_market_enrichment,
    _screening_intent_from_keywords,
    apply_fear_greed_tools,
    build_routing_hint,
    filter_tools_by_route,
)


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "description": name}}


ALL_TOOLS = [
    _tool("get_quote_context"),
    _tool("screen_by_condition"),
    _tool("screen_by_pattern"),
    _tool("screen_reference_peer"),
    _tool("list_screeners"),
    _tool("list_recipes"),
    _tool("run_recipe"),
    _tool("propose_recipe"),
    _tool("propose_screening"),
    _tool("explain_screening_run"),
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
    assert "screen_reference_peer" in names
    assert "list_screeners" in names
    assert "list_recipes" in names
    assert "run_recipe" in names
    assert "propose_screening" in names
    assert "propose_recipe" in names
    assert "explain_screening_run" in names
    assert "run_python" not in names
    assert "read_skill_file" not in names
    assert "get_backtest_result" not in names


def test_filter_diagnosis_excludes_raw_mcp():
    filtered = filter_tools_by_route(
        ALL_TOOLS,
        "diagnosis",
        mcp_tool_names={"mcp_tdx_wenda"},
    )
    names = {t["function"]["name"] for t in filtered}
    assert "diagnose_stock" in names
    assert "mcp_tdx_wenda" not in names


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


def test_screening_intent_style_keywords():
    intraday = _screening_intent_from_keywords("帮我做短线游资选股")
    assert intraday.recipe_id == "intraday_multi"
    assert intraday.confidence == "high"

    post_close = _screening_intent_from_keywords("中线波段机会")
    assert post_close.recipe_id == "post_close_multi"

    value = _screening_intent_from_keywords("长线价投标的")
    assert value.preset == "低 PE"


def test_build_routing_hint_screening_recipe():
    analysis = IntentAnalysis(
        route=IntentRoute(category="screening", confidence="high", reasoning="用户要盘中选股"),
        screening=ScreeningIntent(
            intent="短线游资",
            recipe_id="intraday_multi",
            trigger_kind="intraday",
            top_n=20,
            confidence="high",
        ),
    )
    hint = build_routing_hint(analysis)
    assert "直接 run_recipe（recipe_id=intraday_multi" in hint
    assert "可直接调用 screen_by_condition" not in hint


def test_screening_tool_routing_scheme_name():
    from vnpy_llm.routing.router import _screening_tool_routing_lines

    lines = _screening_tool_routing_lines(
        ScreeningIntent(intent="我的方案", scheme_name="我的 · 低PE", confidence="high"),
    )
    assert any("propose_screening" in line for line in lines)


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
    assert "list_screeners" in hint or "screen_by_condition" in hint
    assert "propose_screening" in hint or "propose_recipe" in hint
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


def test_keyword_fallback_trend_scenario():
    text = "请对 科大讯飞（002230.SZSE） 做走势情景分析（展望 5 日）"
    result = _keyword_fallback(text, "")
    assert result is not None
    assert result.route.category == "technical"


def test_build_routing_hint_trend_scenario():
    text = (
        "请对 科大讯飞（002230.SZSE） 做走势情景分析（非确定性预测，展望 5 日）。"
        "基于本地均线（MA20/MA60）、结构锚点与统计参考带组织分析。"
    )
    analysis = IntentAnalysis(
        route=IntentRoute(category="technical", confidence="high", reasoning="走势情景"),
    )
    hint = build_routing_hint(analysis, user_text=text)
    assert "trend_scenario_summary" in hint
    assert 'symbol="002230.SZSE"' in hint
    assert "horizon_days=5" in hint
    assert "fast_window=20" in hint
    assert "slow_window=60" in hint
    assert "勿再调用 technical_snapshot" in hint
    assert "get_ashare_fear_greed_index" in hint


def test_build_routing_hint_pattern_screen():
    text = "全市场均线多头排列选股 MA5>MA10>MA20>MA60"
    analysis = IntentAnalysis(
        route=IntentRoute(category="screening", confidence="high", reasoning="形态选股"),
        screening=ScreeningIntent(intent=text, top_n=30, confidence="high"),
    )
    hint = build_routing_hint(analysis, user_text=text)
    assert "screen_by_pattern" in hint
    assert 'pattern="均线多头排列"' in hint
    assert "tdx_stock_picker" in hint
    assert "run_python" in hint
