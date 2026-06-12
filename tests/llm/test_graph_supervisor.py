"""Supervisor 与 Agent 工具过滤测试。"""

from __future__ import annotations

from vnpy_llm.graph.handoff import resolve_handoff_agents
from vnpy_llm.graph.supervisor import (
    build_supervisor_decision,
    filter_tools_for_agent,
    resolve_target_agent,
)
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute, MarketEnrichment


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "description": name}}


ALL_TOOLS = [
    _tool("get_quote_context"),
    _tool("diagnose_stock"),
    _tool("screen_by_condition"),
    _tool("get_backtest_result"),
    _tool("run_python"),
    _tool("get_ashare_fear_greed_index"),
    _tool("add_to_watchlist"),
]


def test_resolve_target_agent_mapping():
    assert resolve_target_agent(IntentAnalysis(route=IntentRoute(category="quote"))) == "market"
    assert resolve_target_agent(IntentAnalysis(route=IntentRoute(category="diagnosis"))) == "research"
    assert resolve_target_agent(IntentAnalysis(route=IntentRoute(category="screening"))) == "screening"
    assert resolve_target_agent(IntentAnalysis(route=IntentRoute(category="backtest"))) == "backtest"
    assert resolve_target_agent(IntentAnalysis(route=IntentRoute(category="data"))) == "data"
    assert resolve_target_agent(IntentAnalysis(route=IntentRoute(category="watchlist"))) == "market"


def test_handoff_research_to_market():
    agents, reason = resolve_handoff_agents("diagnosis", "诊断下讯飞，再结合大盘情绪")
    assert agents == ["market"]
    assert "大盘" in reason or "情绪" in reason


def test_handoff_backtest_to_market():
    agents, _ = resolve_handoff_agents("backtest", "解读回测结果，并看下均线信号")
    assert agents == ["market"]


def test_build_supervisor_decision_handoff():
    analysis = IntentAnalysis(
        route=IntentRoute(category="diagnosis", confidence="high"),
        market=MarketEnrichment(fear_greed="highlight"),
    )
    decision = build_supervisor_decision(analysis, "诊断这只票，市场怎么样")
    assert decision.target_agent == "research"
    assert decision.handoff_agents == ["market"]


def test_filter_tools_for_research_agent():
    filtered = filter_tools_for_agent("research", ALL_TOOLS)
    names = {(t["function"]["name"]) for t in filtered}
    assert names == {"get_quote_context", "diagnose_stock"}


def test_filter_tools_for_market_includes_watchlist():
    filtered = filter_tools_for_agent("market", ALL_TOOLS)
    names = {(t["function"]["name"]) for t in filtered}
    assert "add_to_watchlist" in names
    assert "diagnose_stock" not in names
