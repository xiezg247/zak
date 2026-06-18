"""行情 Provider 路由测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.core import provider as provider_module
from vnpy_ashare.quotes.core.provider import (
    QuoteProviderError,
    RedisQuoteProvider,
    TickflowQuoteProvider,
    _merge_richer_quote,
    get_quote_provider,
    get_redis_provider,
    resolve_quote_snapshot,
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


class TestResolveQuoteSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        provider_module._tickflow_provider = None
        provider_module._redis_provider = None

    def test_merge_richer_quote_keeps_base_price(self) -> None:
        base = QuoteSnapshot(
            symbol="600000.SH",
            name="浦发银行",
            last_price=6.71,
            prev_close=6.10,
            open_price=0.0,
            high_price=0.0,
            low_price=0.0,
            change_amount=0.61,
            change_pct=10.0,
            turnover_rate=0.0,
            volume=0.0,
            amount=0.0,
        )
        live = QuoteSnapshot(
            symbol="600000.SH",
            name="浦发银行",
            last_price=6.70,
            prev_close=6.10,
            open_price=6.20,
            high_price=6.71,
            low_price=6.15,
            change_amount=0.60,
            change_pct=9.84,
            turnover_rate=1.23,
            volume=123456.0,
            amount=789000000.0,
            amplitude=9.18,
            trade_time="2026-06-18 15:00:00",
        )
        merged = _merge_richer_quote(base, live)
        self.assertEqual(merged.last_price, 6.71)
        self.assertEqual(merged.open_price, 6.20)
        self.assertEqual(merged.volume, 123456.0)
        self.assertEqual(merged.trade_time, "2026-06-18 15:00:00")

    @patch("vnpy_ashare.quotes.core.provider._fetch_live_quote")
    def test_resolve_enriches_sparse_row_hint(self, fetch_mock: MagicMock) -> None:
        item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
        fetch_mock.return_value = QuoteSnapshot(
            symbol="600000.SH",
            name="浦发银行",
            last_price=6.71,
            prev_close=6.10,
            open_price=6.20,
            high_price=6.71,
            low_price=6.15,
            change_amount=0.61,
            change_pct=10.0,
            turnover_rate=1.23,
            volume=100.0,
            amount=200.0,
            amplitude=9.0,
            trade_time="2026-06-18 15:00:00",
        )
        quote = resolve_quote_snapshot(
            item,
            row_hint={"vt_symbol": item.vt_symbol, "last_price": 6.71, "change_pct": 10.0},
        )
        assert quote is not None
        self.assertEqual(quote.open_price, 6.20)
        self.assertEqual(quote.volume, 100.0)
        fetch_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
