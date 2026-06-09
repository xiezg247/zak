"""行情 Provider 路由测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.quotes import provider as provider_module
from vnpy_ashare.quotes.provider import (
    QuoteProviderError,
    RedisQuoteProvider,
    TickflowQuoteProvider,
    get_quote_provider,
    get_redis_provider,
)


class TestQuoteProviderRouting(unittest.TestCase):
    def setUp(self) -> None:
        provider_module._tickflow_provider = None
        provider_module._redis_provider = None

    def test_watchlist_uses_tickflow(self) -> None:
        provider = get_quote_provider("watchlist")
        self.assertIsInstance(provider, TickflowQuoteProvider)

    @patch.object(provider_module.RedisQuoteStore, "ping", return_value=True)
    def test_market_uses_redis(self, _ping: MagicMock) -> None:
        provider = get_quote_provider("market")
        self.assertIsInstance(provider, RedisQuoteProvider)

    @patch.object(provider_module.RedisQuoteStore, "ping", side_effect=OSError("down"))
    def test_market_redis_unavailable(self, _ping: MagicMock) -> None:
        with self.assertRaises(QuoteProviderError):
            get_redis_provider()


if __name__ == "__main__":
    unittest.main()
