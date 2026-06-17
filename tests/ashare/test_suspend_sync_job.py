"""停牌日同步任务测试。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError
from vnpy_ashare.jobs.sync.suspend_sync import sync_suspend_daily_job


class SuspendSyncJobTests(unittest.TestCase):
    def test_skips_when_token_missing(self) -> None:
        with patch(
            "vnpy_ashare.jobs.sync.suspend_sync.get_tushare_pro",
            side_effect=TushareNotConfiguredError("no token"),
        ):
            result = sync_suspend_daily_job()
        self.assertTrue(result.skipped)

    def test_reports_sync_count(self) -> None:
        with patch("vnpy_ashare.jobs.sync.suspend_sync.get_tushare_pro", return_value=object()):
            with patch(
                "vnpy_ashare.jobs.sync.suspend_sync.sync_suspend_recent",
                return_value=(12, [date(2026, 6, 11), date(2026, 6, 12), date(2026, 6, 13)]),
            ):
                result = sync_suspend_daily_job()
        self.assertTrue(result.success)
        self.assertIn("12", result.message)


if __name__ == "__main__":
    unittest.main()
