"""选股测试共用 fixture。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_market_board_filter_for_tests(monkeypatch):
    """避免本机 QSettings 板块白名单导致 symbol 非 6xx/0xx 的用例被误杀。"""
    inactive = __import__(
        "vnpy_ashare.config.trading_universe",
        fromlist=["MarketBoardFilter"],
    ).MarketBoardFilter(active=False, boards=frozenset())
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.resolve_market_board_filter",
        lambda: inactive,
    )
