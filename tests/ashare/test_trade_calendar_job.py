"""交易日历同步任务测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError
from vnpy_ashare.jobs.trade_calendar import sync_trade_calendar_job


class TradeCalendarJobTests(unittest.TestCase):
    def test_skips_when_token_missing(self) -> None:
        with patch(
            "vnpy_ashare.jobs.trade_calendar.get_tushare_pro",
            side_effect=TushareNotConfiguredError("no token"),
        ):
            result = sync_trade_calendar_job()
        self.assertTrue(result.skipped)

    def test_reports_sync_count(self) -> None:
        with patch("vnpy_ashare.jobs.trade_calendar.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.trade_calendar.sync_trade_calendar",
                return_value=1200,
            ):
                result = sync_trade_calendar_job()
        self.assertTrue(result.success)
        self.assertIn("1200", result.message)


if __name__ == "__main__":
    unittest.main()
