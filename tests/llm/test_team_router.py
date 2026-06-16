"""投研团队路由与命令测试。"""

from __future__ import annotations

from vnpy_llm.routing.router import _keyword_fallback, normalize_team_command


def test_normalize_team_command_with_code():
    assert normalize_team_command("/team 600519") == "对 600519 启动团队全面分析"
    assert normalize_team_command("/team 002230.SZSE") == "对 002230.SZSE 启动团队全面分析"


def test_normalize_team_command_without_code():
    assert normalize_team_command("/team") == "对当前选中标的启动团队全面分析"


def test_normalize_team_command_not_match():
    assert normalize_team_command("全面分析 600519") is None


def test_keyword_fallback_team_analysis():
    result = _keyword_fallback("全面分析 600519", page="")
    assert result is not None
    assert result.route.category == "team_analysis"


def test_keyword_fallback_team_from_expanded_command():
    expanded = normalize_team_command("/team 600519")
    assert expanded is not None
    result = _keyword_fallback(expanded, page="")
    assert result is not None
    assert result.route.category == "team_analysis"
