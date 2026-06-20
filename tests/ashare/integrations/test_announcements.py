"""公告与新闻数据源单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.integrations.akshare.events import fetch_announcements_akshare
from vnpy_ashare.integrations.events.announcements import AnnouncementFetchError, fetch_announcements


class AnnouncementProviderTests(unittest.TestCase):
    @patch("vnpy_ashare.integrations.events.announcements.fetch_announcements_akshare")
    def test_fetch_announcements_prefers_akshare(self, mock_ak: MagicMock) -> None:
        mock_ak.return_value = [{"ann_date": "20250620", "title": "权益分派", "url": "https://example.com"}]
        rows = fetch_announcements("600519.SH", limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "权益分派")
        mock_ak.assert_called_once()

    @patch("vnpy_ashare.integrations.events.announcements._fetch_announcements_tushare")
    @patch("vnpy_ashare.integrations.events.announcements.fetch_announcements_akshare")
    def test_fetch_announcements_falls_back_to_tushare(
        self,
        mock_ak: MagicMock,
        mock_ts: MagicMock,
    ) -> None:
        from vnpy_ashare.integrations.akshare.events import AkshareFetchError

        mock_ak.side_effect = AkshareFetchError("network")
        mock_ts.return_value = [{"ann_date": "20250620", "title": "Tushare 公告", "url": ""}]
        rows = fetch_announcements("600519.SH", limit=5)
        self.assertEqual(rows[0]["title"], "Tushare 公告")

    @patch("vnpy_ashare.integrations.events.announcements._fetch_announcements_tushare")
    @patch("vnpy_ashare.integrations.events.announcements.fetch_announcements_akshare")
    def test_fetch_announcements_raises_when_all_failed(
        self,
        mock_ak: MagicMock,
        mock_ts: MagicMock,
    ) -> None:
        from vnpy_ashare.integrations.akshare.events import AkshareFetchError

        mock_ak.side_effect = AkshareFetchError("network")
        mock_ts.return_value = None
        with self.assertRaises(AnnouncementFetchError):
            fetch_announcements("600519.SH")

    @patch("vnpy_ashare.integrations.akshare.events.parse_stock_symbol")
    def test_akshare_normalizes_rows(self, mock_parse: MagicMock) -> None:
        item = MagicMock()
        item.symbol = "600519"
        mock_parse.return_value = item

        frame = MagicMock()
        frame.empty = False
        frame.to_dict.return_value = [
            {
                "公告标题": "年度权益分派实施公告",
                "公告类型": "分配方案实施",
                "公告日期": "2025-06-20",
                "网址": "https://example.com/a",
            }
        ]

        ak_module = MagicMock()
        ak_module.stock_individual_notice_report.return_value = frame

        with patch.dict("sys.modules", {"akshare": ak_module}):
            rows = fetch_announcements_akshare("600519.SH", days=30, limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ann_date"], "20250620")
        self.assertEqual(rows[0]["title"], "年度权益分派实施公告")
        self.assertEqual(rows[0]["category"], "分配方案实施")


if __name__ == "__main__":
    unittest.main()
