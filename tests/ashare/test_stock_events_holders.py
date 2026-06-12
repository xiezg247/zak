"""事件日历与股东结构单元测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from vnpy_ashare.services.stock.events import EventsProfile, _build_upcoming_hints
from vnpy_ashare.services.stock.holders import build_holder_profile


class StockEventsServiceTests(unittest.TestCase):
    def test_upcoming_hints_disclosure(self) -> None:
        soon = (datetime.now() + timedelta(days=5)).strftime("%Y%m%d")
        profile = EventsProfile(
            ts_code="600519.SH",
            vt_symbol="600519.SSE",
            disclosure=[{"end_date": "20240331", "pre_date": "", "ann_date": soon, "actual_date": ""}],
        )
        hints = _build_upcoming_hints(profile)
        self.assertTrue(any("披露" in item for item in hints))

    @patch("vnpy_ashare.services.stock.holders.fetch_top10_holders")
    def test_build_holder_profile(self, mock_fetch) -> None:
        mock_fetch.return_value = [
            {
                "end_date": "20231231",
                "ann_date": "20240401",
                "holder_name": "贵州茅台集团",
                "hold_amount": 1000.0,
                "hold_ratio": 54.0,
            }
        ]
        profile = build_holder_profile("600519.SSE")
        self.assertEqual(profile.end_date, "20231231")
        self.assertEqual(profile.holders[0]["holder_name"], "贵州茅台集团")


if __name__ == "__main__":
    unittest.main()
