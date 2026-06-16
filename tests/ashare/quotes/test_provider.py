"""行情 Provider 路由测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.quotes.core import provider as provider_module
from vnpy_ashare.quotes.core.provider import (
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

    @patch("vnpy_ashare.quotes.core.provider.fill_missing_tushare_factors")
    @patch("vnpy_ashare.quotes.core.provider.fetch_quotes_from_tickflow", return_value={"600000.SH": MagicMock()})
    def test_tickflow_provider_enriches_tushare_factors(
        self,
        fetch_mock: MagicMock,
        enrich_mock: MagicMock,
    ) -> None:
        provider = get_quote_provider("watchlist")
        quotes = provider.get_quotes([])
        fetch_mock.assert_called_once_with([])
        enrich_mock.assert_called_once_with(quotes)

    @patch.object(provider_module.RedisQuoteStore, "ping", side_effect=OSError("down"))
    def test_market_redis_unavailable(self, _ping: MagicMock) -> None:
        with self.assertRaises(QuoteProviderError):
            get_redis_provider()


if __name__ == "__main__":
    unittest.main()
