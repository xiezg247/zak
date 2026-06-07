"""分 K 周期映射测试。"""

from __future__ import annotations

import unittest
from datetime import timedelta

from vnpy.trader.constant import Interval

from vnpy_ashare.minute_periods import (
    LOCAL_SCOPE_OPTIONS,
    MINUTE_PERIOD,
    bar_interval,
    is_daily_scope,
    normalize_period,
    scope_display,
    storage_interval,
)


class MinutePeriodTests(unittest.TestCase):
    def test_storage_interval(self) -> None:
        self.assertEqual(storage_interval("1m"), Interval.MINUTE.value)

    def test_bar_interval(self) -> None:
        self.assertEqual(bar_interval("1m"), Interval.MINUTE)

    def test_normalize_rejects_other_periods(self) -> None:
        with self.assertRaises(ValueError):
            normalize_period("5m")

    def test_period_step(self) -> None:
        from vnpy_ashare.minute_periods import period_step

        self.assertEqual(period_step("1m"), timedelta(minutes=1))

    def test_local_scope_options(self) -> None:
        self.assertEqual(LOCAL_SCOPE_OPTIONS[0], ("日K", "daily"))
        self.assertEqual(LOCAL_SCOPE_OPTIONS[1], ("1分", MINUTE_PERIOD))
        self.assertFalse(is_daily_scope("1m"))
        self.assertEqual(scope_display("1m"), "1分")


if __name__ == "__main__":
    unittest.main()
