"""投研团队快速模式（预取 + chief）测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy_llm.graph.orchestrator import (
    _prefetch_bundle_ready,
    stream_team_analysis,
)
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute


def test_prefetch_bundle_ready():
    assert _prefetch_bundle_ready(
        {
            "financial": {"roe": 1},
            "risk": {"vol": 1},
            "strategy": {"ma": 1},
        }
    )
    assert not _prefetch_bundle_ready({"financial": {"error": "x"}, "risk": {}, "strategy": {}})
    assert not _prefetch_bundle_ready(None)


def test_stream_team_analysis_fast_mode_skips_sub_agents(monkeypatch):
    monkeypatch.setattr("vnpy_llm.graph.orchestrator.team_deep_mode_enabled", lambda: False)

    sample_prefetch = {
        "symbol": "600519.SSE",
        "name": "贵州茅台",
        "financial": {"latest_financials": {"roe": 20}, "valuation": {"pe_ttm": 25}},
        "risk": {"volatility_annualized_pct": 22, "max_drawdown_pct": 15},
        "strategy": {"technical": {"ma_alignment": "均线多头"}, "strategy_signals": {"signal": "buy"}},
        "diagnose": {"available": False},
        "market_context": {"summary_lines": ["上证 +0.5%"]},
    }

    chief_calls: list[str] = []

    def fake_stream_agent(config, messages, tools, tool_executor, **kwargs):
        del config, tools, tool_executor, kwargs
        user = messages[-1]["content"]
        chief_calls.append(user)
        yield "综合结论：观望。"

    monkeypatch.setattr("vnpy_llm.graph.orchestrator._stream_agent", fake_stream_agent)
    monkeypatch.setattr(
        "vnpy_llm.graph.orchestrator._resolve_symbol",
        lambda _ctx: "600519.SSE",
    )

    scores = {
        "financial": {"score": 70, "summary": "盈利稳健", "highlights": ["ROE 20%"], "risks": []},
        "risk": {"score": 65, "summary": "波动可控", "highlights": [], "risks": []},
        "strategy": {"score": 80, "summary": "均线多头", "highlights": ["偏多"], "risks": []},
        "market": {"score": 72, "summary": "跑赢大盘", "highlights": [], "risks": []},
        "weighted": 72.5,
    }
    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="team_analysis")),
        user_text="全面分析 600519",
        team_prefetch=sample_prefetch,
        team_scores=scores,
    )

    output = "".join(
        stream_team_analysis(
            MagicMock(configured=True),
            [{"role": "user", "content": "全面分析"}],
            [],
            MagicMock(),
            graph_ctx=graph_ctx,
        )
    )

    assert "快速团队" in output
    assert "行情" in output
    assert "## 财务面" in output
    assert "## 风险面" in output
    assert "## 策略面" in output
    assert "规则参考分" in output
    assert "规则速览" in output
    assert "## 综合研判" in output
    assert "综合结论：观望。" in output
    assert chief_calls, "chief 应被调用一次"
    assert "子分析师输出" in chief_calls[0]
