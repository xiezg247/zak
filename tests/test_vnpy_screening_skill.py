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
    assert "propose_screening" in result["note"]


def test_screen_by_condition_no_data():
    svc = MagicMock()
    from vnpy_ashare.ai.context_store import clear_all

    clear_all()
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜"))
    assert result["status"] == "blocked"
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
