"""universe 板块过滤 SQL 参数化（PostgreSQL LIKE % 兼容）。"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401
from vnpy_ashare.storage.repositories.universe import count_universe, load_universe_page


def test_count_universe_main_board() -> None:
    total = count_universe("沪深主板")
    assert total > 0


def test_load_universe_page_main_board() -> None:
    rows, total = load_universe_page(offset=0, limit=10, board="沪深主板")
    assert total > 0
    assert len(rows) > 0
    for symbol, _exchange, _name in rows:
        assert symbol.startswith(("600", "601", "603", "000", "001", "002", "003"))
