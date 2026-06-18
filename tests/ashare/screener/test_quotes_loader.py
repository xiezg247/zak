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


if __name__ == "__main__":
    unittest.main()
