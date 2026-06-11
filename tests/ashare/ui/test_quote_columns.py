"""行情表列格式化测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_ashare.ui.quotes.table.columns import (
    build_quote_row,
    format_amount,
    format_volume,
    quote_column_index,
)


class TestQuoteColumns(unittest.TestCase):
    def test_formatters(self) -> None:
        self.assertEqual(format_volume(3_1304), "3.13万")
        self.assertEqual(format_amount(3_984_001_900), "39.84亿")

    def test_build_quote_row(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        quote = QuoteSnapshot(
            symbol="600519.SH",
            name="贵州茅台",
            last_price=1272.86,
            prev_close=1268.0,
            open_price=1278.0,
            high_price=1283.0,
            low_price=1267.74,
            change_amount=4.86,
            change_pct=0.38,
            turnover_rate=0.25,
            volume=31304,
            amount=3_984_001_900,
            amplitude=1.20,
            trade_time="2026-06-05 15:00:02",
        )
        values, colored = build_quote_row(item, quote, "1", "✓")
        self.assertEqual(values[0], "1")
        self.assertEqual(values[3], "贵州茅台")
        self.assertIn("39.84亿", values)
        self.assertEqual(values[quote_column_index("trade_time")], "15:00:02")
        self.assertEqual(values[-1], "✓")
        self.assertIn(4, colored)


class TestMarketAutoRefreshPref(unittest.TestCase):
    def test_default_is_true_when_unset(self) -> None:
        from vnpy.trader.ui import QtCore

        from vnpy_ashare.ui.quotes.page.config import (
            MARKET_AUTO_REFRESH_DEFAULT,
            MARKET_AUTO_REFRESH_SETTINGS_KEY,
            load_market_auto_refresh_pref,
        )

        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        settings.remove(MARKET_AUTO_REFRESH_SETTINGS_KEY)
        self.assertTrue(MARKET_AUTO_REFRESH_DEFAULT)
        self.assertTrue(load_market_auto_refresh_pref())


class TestQuoteRefreshHint(unittest.TestCase):
    def test_refresh_hint(self) -> None:
        from vnpy_ashare.ui.quotes.page.config import (
            MARKET_QUOTE_REFRESH_MS,
            PAGE_CONFIGS,
            WATCHLIST_QUOTE_REFRESH_MS,
            quote_refresh_hint,
            quote_refresh_seconds,
        )

        self.assertEqual(quote_refresh_seconds(MARKET_QUOTE_REFRESH_MS), 15)
        self.assertEqual(quote_refresh_seconds(WATCHLIST_QUOTE_REFRESH_MS), 3)
        self.assertEqual(
            quote_refresh_hint(
                auto_refresh=True,
                refresh_ms=MARKET_QUOTE_REFRESH_MS,
                quote_source="market",
            ),
            "行情每 15 秒自动刷新（Redis，交易时段）",
        )
        self.assertEqual(
            quote_refresh_hint(
                auto_refresh=True,
                refresh_ms=WATCHLIST_QUOTE_REFRESH_MS,
                quote_source="watchlist",
            ),
            "行情/五档 WebSocket，图表每 3 秒刷新（交易时段）",
        )
        self.assertEqual(
            quote_refresh_hint(
                auto_refresh=True,
                refresh_ms=MARKET_QUOTE_REFRESH_MS,
                paused_for_hours=True,
            ),
            "非交易时段，行情暂停自动刷新",
        )
        self.assertEqual(
            quote_refresh_hint(auto_refresh=False, refresh_ms=MARKET_QUOTE_REFRESH_MS),
            "行情不自动刷新",
        )
        self.assertEqual(PAGE_CONFIGS["市场"].quote_source, "market")
        self.assertTrue(PAGE_CONFIGS["市场"].market_full_list)
        self.assertTrue(PAGE_CONFIGS["市场"].auto_refresh_quotes)
        self.assertEqual(PAGE_CONFIGS["市场"].market_live_display_limit, 100)
        self.assertEqual(PAGE_CONFIGS["自选"].quote_source, "watchlist")
        rankings = PAGE_CONFIGS["榜单"]
        self.assertTrue(rankings.show_rank_sidebar)
        self.assertTrue(rankings.use_market_rank)
        self.assertEqual(rankings.default_rank_id, "change_pct")


class TestQuoteSourceLabel(unittest.TestCase):
    def test_quote_source_labels(self) -> None:
        from vnpy_ashare.ui.quotes.page.config import PAGE_CONFIGS, quote_source_label

        market = PAGE_CONFIGS["市场"]
        watchlist = PAGE_CONFIGS["自选"]
        local = PAGE_CONFIGS["本地"]

        self.assertEqual(
            quote_source_label(market),
            "行情源：Redis",
        )
        self.assertEqual(
            quote_source_label(watchlist, stream_active=True),
            "行情源：TickFlow (WebSocket)",
        )
        self.assertEqual(
            quote_source_label(watchlist, stream_active=False),
            "行情源：TickFlow",
        )
        self.assertEqual(quote_source_label(local), "行情源：本地 K 线")
        self.assertEqual(
            quote_source_label(watchlist, gateway_active=True),
            "行情源：Gateway",
        )


if __name__ == "__main__":
    unittest.main()
