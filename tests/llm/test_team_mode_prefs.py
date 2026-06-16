"""投研团队部分预取与模式偏好测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy_llm.config.team_prefs import load_team_deep_mode_pref, save_team_deep_mode_pref
from vnpy_llm.graph.orchestrator import (
    MIN_FAST_PREFETCH_AGENTS,
    _ready_prefetch_agents,
    stream_team_analysis,
)
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute


def test_ready_prefetch_agents_partial():
    ready = _ready_prefetch_agents(
        {
            "financial": {"latest_financials": {"roe": 10}},
            "risk": {"error": "no bars"},
            "strategy": {"technical": {"ma_alignment": "多头"}},
        }
    )
    assert ready == ("financial", "strategy")
    assert len(ready) >= MIN_FAST_PREFETCH_AGENTS


def test_stream_team_analysis_partial_prefetch_fast_mode(monkeypatch):
    monkeypatch.setattr("vnpy_llm.graph.orchestrator.team_deep_mode_enabled", lambda: False)

    sample_prefetch = {
        "symbol": "600519.SSE",
        "financial": {"latest_financials": {"roe": 20}, "valuation": {"pe_ttm": 25}},
        "risk": {"error": "no local bars"},
        "strategy": {"technical": {"ma_alignment": "均线多头"}, "strategy_signals": {"signal": "buy"}},
        "market_context": {"stock_vs_benchmark": {"excess_pct": 4.0}, "summary_lines": ["超额 +4%"]},
    }

    monkeypatch.setattr(
        "vnpy_llm.graph.orchestrator._stream_agent",
        lambda *args, **kwargs: (yield "综合结论。"),
    )
    monkeypatch.setattr("vnpy_llm.graph.orchestrator._resolve_symbol", lambda _ctx: "600519.SSE")

    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="team_analysis")),
        user_text="全面分析 600519",
        team_prefetch=sample_prefetch,
        team_scores={
            "financial": {"score": 70, "summary": "ok", "highlights": [], "risks": []},
            "risk": {"score": 0, "summary": "缺失", "highlights": [], "risks": []},
            "strategy": {"score": 80, "summary": "ok", "highlights": [], "risks": []},
            "market": {"score": 60, "summary": "ok", "highlights": [], "risks": []},
            "weighted": 55.0,
        },
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

    assert "部分维度预取缺失" in output
    assert "规则速览不可用" in output
    assert "## 风险面" in output


def test_team_deep_mode_pref_roundtrip():
    save_team_deep_mode_pref(True)
    assert load_team_deep_mode_pref() is True
    save_team_deep_mode_pref(False)
    assert load_team_deep_mode_pref() is False
