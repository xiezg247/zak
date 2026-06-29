"""日 K tail LRU 与 enrich Job 测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.data import pattern_bars
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.jobs.quotes.enrich import enrich_market_quotes


class DailyBarsLruTests(unittest.TestCase):
    def setUp(self) -> None:
        pattern_bars.clear_daily_bars_lru_cache()

    def tearDown(self) -> None:
        pattern_bars.clear_daily_bars_lru_cache()

    def test_batch_hits_lru_on_repeat(self) -> None:
        item = StockItem(symbol="000001", exchange=Exchange.SZSE, name="测试")
        bars = [MagicMock()]
        with patch.object(pattern_bars, "load_daily_bars_tail", return_value=bars) as load_tail:
            first = pattern_bars.load_daily_bars_batch([item], lookback_bars=25, max_workers=1)
            second = pattern_bars.load_daily_bars_batch([item], lookback_bars=25, max_workers=1)
        self.assertIs(first[(item.symbol, item.exchange)], bars)
        self.assertIs(second[(item.symbol, item.exchange)], bars)
        self.assertEqual(load_tail.call_count, 1)


class EnrichMarketQuotesJobTests(unittest.TestCase):
    def test_skips_when_defer_disabled(self) -> None:
        prev = os.environ.pop("ZAK_COLLECT_DEFER_ENRICH", None)
        try:
            result = enrich_market_quotes()
        finally:
            if prev is None:
                os.environ.pop("ZAK_COLLECT_DEFER_ENRICH", None)
            else:
                os.environ["ZAK_COLLECT_DEFER_ENRICH"] = prev
        self.assertTrue(result.skipped)


if __name__ == "__main__":
    unittest.main()
