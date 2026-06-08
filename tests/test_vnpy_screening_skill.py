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
    """向 session_context 注入缓存行情（替代实际行情页数据源）。"""
    from vnpy_ashare.ai.session_context import set_market_quotes_cache

    set_market_quotes_cache(rows, {})


def test_list_screeners():
    svc = MagicMock()
    svc.list_screeners.return_value = ["涨幅榜", "换手率排行", "成交量放大"]
    skill = _make_skill(svc)
    result = json.loads(skill.list_screeners())
    assert result["count"] == 3
    assert "涨幅榜" in result["screeners"]


def test_screen_by_condition_no_data():
    svc = MagicMock()
    from vnpy_ashare.ai.session_context import clear_session_context

    clear_session_context()
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜"))
    assert "暂无可用的市场行情数据" in result["message"]


def test_screen_by_condition_with_data():
    svc = MagicMock()
    svc.screen_by_condition.return_value = [
        {"symbol": "000001", "name": "平安银行", "last_price": 10.5, "change_pct": 3.2}
    ]

    _set_cache([{"symbol": "000001", "name": "平安银行", "vt_symbol": "000001.SZSE"}])

    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜", top_n=10))
    assert result["condition"] == "涨幅榜"
    assert result["count"] == 1
    assert result["results"][0]["symbol"] == "000001"


def test_screen_by_condition_no_match():
    svc = MagicMock()
    svc.screen_by_condition.return_value = []

    _set_cache([{"symbol": "000001", "name": "平安银行"}])

    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜"))
    assert "未匹配到标的" in result["message"]
