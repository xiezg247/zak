"""新闻数据源单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.integrations.akshare.events import fetch_stock_news_akshare
from vnpy_ashare.integrations.events.news import NewsFetchError, fetch_stock_news
from vnpy_ashare.services.stock.news import get_stock_news_for_symbol


class StockNewsProviderTests(unittest.TestCase):
    @patch("vnpy_ashare.integrations.events.news.fetch_stock_news_akshare")
    def test_fetch_stock_news(self, mock_ak: MagicMock) -> None:
        mock_ak.return_value = [{"pub_time": "20250618", "title": "测试新闻", "source": "证券时报", "url": "https://example.com"}]
        rows = fetch_stock_news("600519.SH", limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "测试新闻")

    @patch("vnpy_ashare.integrations.events.news.fetch_stock_news_akshare")
    def test_fetch_stock_news_raises(self, mock_ak: MagicMock) -> None:
        from vnpy_ashare.integrations.akshare.events import AkshareFetchError

        mock_ak.side_effect = AkshareFetchError("network")
        with self.assertRaises(NewsFetchError):
            fetch_stock_news("600519.SH")

    @patch("vnpy_ashare.services.stock.news.fetch_stock_news")
    def test_get_stock_news_for_symbol(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [{"pub_time": "20250618", "title": "测试", "source": "东财", "url": ""}]
        result = get_stock_news_for_symbol("600519.SSE", limit=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)

    @patch("vnpy_ashare.integrations.akshare.events.parse_stock_symbol")
    def test_akshare_news_normalizes_rows(self, mock_parse: MagicMock) -> None:
        item = MagicMock()
        item.symbol = "600519"
        mock_parse.return_value = item

        frame = MagicMock()
        frame.empty = False
        frame.to_dict.return_value = [
            {
                "新闻标题": "茅台发布权益分派公告",
                "新闻内容": "摘要内容",
                "发布时间": "2026-06-18 10:50:00",
                "文章来源": "证券时报网",
                "新闻链接": "https://example.com/news",
            }
        ]

        ak_module = MagicMock()
        ak_module.stock_news_em.return_value = frame

        with patch.dict("sys.modules", {"akshare": ak_module}):
            rows = fetch_stock_news_akshare("600519.SH", limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pub_time"], "20260618")
        self.assertEqual(rows[0]["title"], "茅台发布权益分派公告")
        self.assertEqual(rows[0]["source"], "证券时报网")


if __name__ == "__main__":
    unittest.main()
