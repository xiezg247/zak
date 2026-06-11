"""VnpyScreeningSkill 单元测试。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from skills.vnpy_screening_skill import VnpyScreeningSkill


def _make_skill(screening_svc: MagicMock) -> VnpyScreeningSkill:
    skill = VnpyScreeningSkill()
    skill._services = {"screening": screening_svc}
    return skill


def _set_cache(rows: list[dict]) -> None:
    """向 context_store 注入缓存行情（替代实际行情页数据源）。"""
    from vnpy_ashare.ai.context import set_market_quotes_cache

    set_market_quotes_cache(rows, {})


def test_list_screeners():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.list_screeners())
    assert result["count"] >= 3
    assert "涨幅榜" in result["screeners"]
    assert "catalog" in result
    assert "screen_by_condition" in result["note"]
    assert "patterns" in result
    assert "screen_by_pattern" in result["note"]


def test_screen_by_condition_no_data():
    svc = MagicMock()
    svc.run_request.side_effect = RuntimeError("暂无可用的市场行情数据")
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜"))
    assert result["status"] == "error"


def test_screen_by_condition_ok():
    from vnpy_ashare.screener.run.runner import ScreenerRunResult

    svc = MagicMock()
    svc.run_request.return_value = ScreenerRunResult(
        rows=[
            {
                "symbol": "000001",
                "name": "平安银行",
                "vt_symbol": "000001.SZSE",
                "change_pct": 5.2,
            }
        ],
        condition="涨幅榜",
        updated_at="2026-06-09",
        total_scanned=100,
        source="quote",
    )
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜", top_n=5))
    assert result["status"] == "ok"
    assert result["count"] == 1
    svc.persist_run_result.assert_called_once()


def test_screen_by_condition_saved_scheme_not_found():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.screen_by_condition("我的 · 测试"))
    assert result["status"] == "error"
    assert "未找到" in result["message"]


def test_screen_by_pattern_ok():
    from vnpy_ashare.screener.run.runner import ScreenerRunResult

    svc = MagicMock()
    svc.run_pattern_screen.return_value = ScreenerRunResult(
        rows=[
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "vt_symbol": "600519.SSE",
                "pattern_score": 12.5,
                "pattern_hint": "MA5>MA10>MA20>MA60",
            }
        ],
        condition="形态 · 均线多头",
        updated_at="2026-06-09",
        total_scanned=50,
        source="bar",
    )
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_pattern("均线多头", top_n=5))
    assert result["status"] == "ok"
    assert result["pattern"] == "ma_bull"
    assert result["count"] == 1
    svc.persist_run_result.assert_called_once()


def test_screen_by_pattern_unknown():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.screen_by_pattern("头肩顶"))
    assert result["status"] == "error"
    assert "未知形态" in result["message"]


def test_list_recipes():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.list_recipes(trigger_kind="intraday"))
    assert result["count"] >= 1
    assert any(item["recipe_id"] == "intraday_multi" for item in result["recipes"])


def test_run_recipe_ok():
    from vnpy_ashare.screener.run.runner import ScreenerRunResult

    svc = MagicMock()
    svc.run_recipe.return_value = ScreenerRunResult(
        rows=[
            {
                "symbol": "600000",
                "name": "浦发银行",
                "vt_symbol": "600000.SSE",
                "composite_score": 85.0,
                "hit_reason": "动量；换手",
                "dimensions": {"momentum": 90.0, "turnover": 80.0},
            }
        ],
        condition="AI · 盘中多因子",
        updated_at="2026-06-10",
        total_scanned=100,
        source="recipe",
    )
    skill = _make_skill(svc)
    result = json.loads(skill.run_recipe("intraday_multi", top_n=5))
    assert result["status"] == "ok"
    assert result["count"] == 1
    svc.persist_run_result.assert_called_once()


def test_custom_without_threshold_error():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.screen_by_condition("自定义筛选"))
    assert result["status"] == "error"
    assert "min_change_pct" in result["message"] or "阈值" in result["message"]
