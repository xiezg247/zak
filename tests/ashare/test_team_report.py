"""投研团队研报持久化测试。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.services.analysis_detail.team_report import persist_team_analysis_report
from vnpy_ashare.storage.repositories import stock_analysis_reports as repo


def test_persist_team_analysis_report(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "init_app_db", lambda: None)

    captured: dict = {}

    def _fake_create_report(symbol, exchange, **kwargs):
        captured.update(kwargs)
        captured["symbol"] = symbol
        captured["exchange"] = exchange
        return {"id": 42, **kwargs}

    monkeypatch.setattr(repo, "create_report", _fake_create_report)

    body = "## 财务面\n...\n\n---\n\n## 综合研判\n\n结论示例"
    row = persist_team_analysis_report(
        "600519.SSE",
        body,
        name="贵州茅台",
        team_scores={"weighted": 72.5},
    )

    assert row is not None
    assert row["id"] == 42
    assert captured["symbol"] == "600519"
    assert captured["exchange"] == Exchange.SSE
    assert captured["source_scope"] == "team_analysis"
    assert "team_scores" in captured["context_json"]


def test_persist_team_analysis_report_skips_incomplete():
    assert persist_team_analysis_report("600519", "仅子分析师输出") is None
