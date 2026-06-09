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
    from vnpy_ashare.ai.context_store import set_market_quotes_cache

    set_market_quotes_cache(rows, {})


def test_list_screeners():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.list_screeners())
    assert result["count"] >= 3
    assert "涨幅榜" in result["screeners"]
    assert "catalog" in result
    assert "screen_by_condition" in result["note"]


def test_screen_by_condition_no_data():
    svc = MagicMock()
    svc.run_request.side_effect = RuntimeError("暂无可用的市场行情数据")
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜"))
    assert result["status"] == "error"


def test_screen_by_condition_ok():
    from vnpy_ashare.screener.runner import ScreenerRunResult

    svc = MagicMock()
    svc.run_request.return_value = ScreenerRunResult(
        rows=[{
            "symbol": "000001",
            "name": "平安银行",
            "vt_symbol": "000001.SZSE",
            "change_pct": 5.2,
        }],
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


def test_screen_by_condition_need_confirm():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.screen_by_condition("我的 · 测试"))
    assert result["status"] == "need_confirm"
    assert "propose_screening" in result["message"]


def test_propose_screening_builtin():
    from unittest.mock import patch

    skill = _make_skill(MagicMock())
    with patch("vnpy_ashare.screener.nl_mapper.collect_warnings", return_value=[]):
        result = json.loads(
            skill.propose_screening("今天涨最多的", preset="涨幅榜", top_n=5, confidence="high")
        )
    assert result["status"] == "pending_confirm"
    assert result["draft_id"]
    assert result["preset"] == "涨幅榜"
