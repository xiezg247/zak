"""Market Agent 路由与命令测试。"""

from __future__ import annotations

from vnpy_ashare.ai.context.market_overview import build_intraday_environment_prompt
from vnpy_llm.graph.market_orchestrator import format_market_prefetch_block, prefetch_market_facts
from vnpy_llm.graph.supervisor import resolve_target_agent
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute
from vnpy_llm.routing.router import (
    _keyword_fallback,
    filter_tools_by_route,
    normalize_market_command,
)
from vnpy_llm.routing.prompts import build_page_prompt


def _tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "description": name}}


ALL_TOOLS = [
    _tool("get_emotion_cycle"),
    _tool("check_risk_gate"),
    _tool("get_ashare_fear_greed_index"),
    _tool("run_leader_screen"),
    _tool("get_short_term_watchlist"),
    _tool("get_quote_context"),
    _tool("diagnose_stock"),
]


def test_normalize_market_command_intraday():
    assert normalize_market_command("/market") is not None
    assert "极致短线" in normalize_market_command("/market") or ""


def test_normalize_market_command_environment():
    text = normalize_market_command("/market environment")
    assert text is not None
    assert "大盘" in text or "环境" in text


def test_keyword_fallback_market_from_quick_action_prompt():
    prompt = build_intraday_environment_prompt()
    result = _keyword_fallback(prompt, page="市场")
    assert result is not None
    assert result.route.category == "market"


def test_keyword_fallback_market_intraday_question():
    result = _keyword_fallback("今天能不能做短线", page="")
    assert result is not None
    assert result.route.category == "market"


def test_resolve_target_agent_market():
    analysis = IntentAnalysis(route=IntentRoute(category="market"))
    assert resolve_target_agent(analysis) == "market"


def test_filter_tools_by_route_market_subset():
    filtered = filter_tools_by_route(ALL_TOOLS, "market")
    names = {t["function"]["name"] for t in filtered}
    assert "get_emotion_cycle" in names
    assert "check_risk_gate" in names
    assert "diagnose_stock" not in names


def test_build_page_prompt_market_includes_dynamic_block():
    prompt = build_page_prompt("市场")
    assert "市场页" in prompt or "【市场页】" in prompt
    assert "get_emotion_cycle" in prompt or "终端已注入摘要" in prompt


def test_prefetch_market_facts_calls_executor():
    calls: list[str] = []

    def executor(name: str, arguments: dict) -> str:
        calls.append(name)
        return f'{{"tool": "{name}"}}'

    payload = prefetch_market_facts(executor)
    assert set(calls) == {"get_emotion_cycle", "check_risk_gate", "get_ashare_fear_greed_index"}
    block = format_market_prefetch_block(payload)
    assert "情绪周期" in block
    assert "get_emotion_cycle" in block
