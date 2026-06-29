"""quotes_loader Redis 容错测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import redis

import tests._bootstrap  # noqa: F401
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows


class QuotesLoaderRedisTests(unittest.TestCase):
    @patch("vnpy_ashare.screener.data.quotes_loader.RedisQuoteStore")
    def test_wraps_redis_timeout_as_market_quotes_load_error(self, store_cls: MagicMock) -> None:
        store = store_cls.return_value
        store.list_all_rank_symbols.return_value = ["000001.SZ"]
        store.get_quotes.side_effect = redis.TimeoutError("Timeout writing to socket")

        with self.assertRaises(MarketQuotesLoadError) as ctx:
            load_market_quote_rows()

        self.assertIn("Redis 行情读取失败", str(ctx.exception))

    @patch("vnpy_ashare.screener.data.quotes_loader.RedisQuoteStore")
    def test_wraps_list_symbols_redis_error(self, store_cls: MagicMock) -> None:
        store_cls.return_value.list_all_rank_symbols.side_effect = redis.ConnectionError("Connection refused")

        with self.assertRaises(MarketQuotesLoadError) as ctx:
            load_market_quote_rows()

        self.assertIn("Redis 行情读取失败", str(ctx.exception))

    @patch("vnpy_ashare.screener.data.quotes_loader._load_from_l1", return_value=None)
    @patch("vnpy_ashare.screener.data.quotes_loader.RedisQuoteStore")
    def test_loads_rows_from_redis(self, store_cls: MagicMock, _l1: MagicMock) -> None:
        from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot

        store = store_cls.return_value
        store.list_all_rank_symbols.return_value = ["000001.SZ"]
        store.get_quotes.return_value = {
            "000001.SZ": QuoteSnapshot(
                symbol="000001",
                name="平安",
                last_price=10.0,
                prev_close=9.9,
                open_price=9.9,
                high_price=10.1,
                low_price=9.8,
                change_amount=0.1,
                change_pct=1.0,
                turnover_rate=1.0,
                volume=1000.0,
            ),
        }
        store.get_updated_at.return_value = "2026-06-26 10:00:00"

        snapshot = load_market_quote_rows(enrich_factors=False)
        self.assertEqual(snapshot.total, 1)
        self.assertEqual(snapshot.source, "quote")
        self.assertEqual(snapshot.rows[0]["symbol"], "000001")


if __name__ == "__main__":
    unittest.main()
