"""选股测试共用 fixture。"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "enable_market_board_filter: 使用真实市场板块白名单（默认关闭以免本机 .env 误杀）",
    )


@pytest.fixture(autouse=True)
def disable_market_board_filter_for_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """避免本机 .env / 偏好里的板块白名单导致非主板 symbol 用例被误杀。"""
    if request.node.get_closest_marker("enable_market_board_filter"):
        return
    inactive = __import__(
        "vnpy_ashare.config.trading_universe",
        fromlist=["MarketBoardFilter"],
    ).MarketBoardFilter(active=False, boards=frozenset())
    monkeypatch.setattr(
        "vnpy_ashare.screener.hard_filters.resolve_market_board_filter",
        lambda *args, **kwargs: inactive,
    )
