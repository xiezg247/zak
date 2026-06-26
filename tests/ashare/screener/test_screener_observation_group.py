"""选股结果加入自选池测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from tests.ashare.pg_unittest import PgStorageTestCase
from vnpy_ashare.services.watchlist_short_term import add_screener_rows_to_watchlist_pool
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo


class _WatchlistServiceStub:
    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        return watchlist_repo.add_watchlist_item(symbol, exchange, name)

    def add_failure_reason(self, symbol: str, exchange: Exchange):
        return watchlist_repo.watchlist_add_failure_reason(symbol, exchange)


class TestScreenerWatchlistPool(PgStorageTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.service = _WatchlistServiceStub()

    def test_add_screener_dict_rows(self) -> None:
        rows = [{"vt_symbol": "600519.SSE", "name": "贵州茅台"}]
        result = add_screener_rows_to_watchlist_pool(self.service, rows)
        self.assertEqual(result.watchlist_added, 1)
        self.assertTrue(watchlist_repo.watchlist_contains("600519", Exchange.SSE))
