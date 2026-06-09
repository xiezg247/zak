"""意图路由单元测试。"""

from __future__ import annotations

from vnpy_llm.intent import BacktestIntent, IntentAnalysis, IntentRoute, ScreeningIntent
from vnpy_llm.routing import (
    build_routing_hint,
    filter_tools_by_route,
    _keyword_fallback,
)


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "description": name}}


ALL_TOOLS = [
    _tool("get_quote_context"),
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
    assert "propose_screening" in hint
    assert "涨幅榜" in hint
    assert "选股" in hint


def test_build_routing_hint_backtest():
    analysis = IntentAnalysis(
        route=IntentRoute(category="backtest", confidence="medium"),
        backtest=BacktestIntent(action="list_history", history_limit=5),
    )
    hint = build_routing_hint(analysis)
    assert "list_backtest_history" in hint
    assert "list_history" in hint
