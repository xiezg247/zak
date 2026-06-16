"""投研团队 symbol 解析与 orchestrator 辅助函数测试。"""

from __future__ import annotations

from vnpy_llm.graph.orchestrator import (
    AgentResult,
    _build_agent_task_spec,
    _build_team_context_for_chief,
    _extract_json_from_text,
    _strip_json_blocks,
)
from vnpy_llm.graph.state import GraphStreamContext
from vnpy_llm.graph.team_symbol import normalize_symbol_code, resolve_team_symbol
from vnpy_llm.routing.intent import IntentAnalysis, IntentRoute


def test_normalize_symbol_code_with_exchange():
    assert normalize_symbol_code("600519.SSE") == "600519.SSE"
    assert normalize_symbol_code("002230.SZSE") == "002230.SZSE"
    assert normalize_symbol_code("300750.SZ") == "300750.SZSE"


def test_normalize_symbol_code_infers_exchange():
    assert normalize_symbol_code("600519") == "600519.SSE"
    assert normalize_symbol_code("002230") == "002230.SZSE"
    assert normalize_symbol_code("300750") == "300750.SZSE"


def test_resolve_team_symbol_from_user_text():
    assert resolve_team_symbol(user_text="全面分析 600519") == "600519.SSE"
    assert resolve_team_symbol(user_text="深入评估 002230.SZSE") == "002230.SZSE"


def test_resolve_team_symbol_from_context():
    assert resolve_team_symbol(
        user_text="全面分析这只票",
        context_symbol="600519",
        context_exchange="SSE",
    ) == "600519.SSE"
    assert resolve_team_symbol(
        user_text="团队分析",
        context_symbol="002230",
        context_exchange="深交所",
    ) == "002230.SZSE"


def test_extract_json_from_text():
    text = "## 财务面\n评分 78\n```json\n{\"financial\": {\"score\": 78}}\n```"
    data = _extract_json_from_text(text)
    assert data == {"financial": {"score": 78}}


def test_strip_json_blocks():
    text = "分析正文\n```json\n{\"risk\": {\"score\": 65}}\n```"
    assert _strip_json_blocks(text) == "分析正文"


def test_build_team_context_for_chief_includes_structured_score():
    results = {
        "financial": AgentResult(
            agent="financial",
            markdown="## 财务面\n```json\n{\"financial\": {\"score\": 80}}\n```",
            json_data={"financial": {"score": 80}},
        ),
        "risk": AgentResult(agent="risk", markdown="风险偏高", json_data=None),
        "strategy": AgentResult(agent="strategy", timed_out=True),
    }
    team_scores = {"financial": {"score": 80}, "weighted": 72.5}
    context = _build_team_context_for_chief(results, "行情摘要：涨 1.2%", team_scores)
    assert "结构化评分" in context
    assert "规则评分参考" in context
    assert "风险偏高" in context
    assert "超时未完成" in context
    assert "行情摘要" in context
    assert "```json" not in context


def test_build_agent_task_spec_prefetch_mode():
    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="team_analysis")),
        user_text="/team 600519",
        team_prefetch={
            "financial": {"symbol": "600519.SSE", "latest_financials": {"roe": 18.0}},
            "risk": {"volatility_annualized_pct": 22.0},
            "strategy": {"technical": {"ma_alignment": "多头"}},
        },
        team_scores={
            "financial": {"score": 85, "summary": "ROE 18%"},
            "risk": {"score": 70, "summary": "波动适中"},
            "strategy": {"score": 75, "summary": "多头"},
        },
    )
    spec = _build_agent_task_spec("financial", "600519.SSE", graph_ctx)
    assert spec.use_tools is False
    assert spec.max_rounds == 1
    assert "已预取数据" in spec.user_msg["content"]
    assert "85" in spec.user_msg["content"]


def test_build_agent_task_spec_tool_mode_when_no_prefetch():
    graph_ctx = GraphStreamContext(
        analysis=IntentAnalysis(route=IntentRoute(category="team_analysis")),
        user_text="/team 600519",
    )
    spec = _build_agent_task_spec("financial", "600519.SSE", graph_ctx)
    assert spec.use_tools is True
    assert spec.max_rounds == 3
    assert "必须先调用工具" in spec.user_msg["content"]
