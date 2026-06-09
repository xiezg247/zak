"""本地 K 线健康状态测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime

from vnpy_ashare.bar_health import (
    BarHealthStatus,
    BarMeta,
    find_gaps,
    format_gap_ranges,
    inspect_bar_gaps,
    list_status,
    merge_missing_days,
    status_label,
)
from vnpy_ashare.calendar import is_trading_day, last_trading_day, trading_days_between


class CalendarTests(unittest.TestCase):
    def test_weekend_is_not_trading_day(self) -> None:
        self.assertFalse(is_trading_day(date(2026, 6, 6)))

    def test_weekday_is_trading_day(self) -> None:
        self.assertTrue(is_trading_day(date(2026, 6, 5)))

    def test_last_trading_day_skips_weekend(self) -> None:
        self.assertEqual(last_trading_day(on_or_before=date(2026, 6, 7)), date(2026, 6, 5))

    def test_trading_days_between(self) -> None:
        days = trading_days_between(date(2026, 6, 1), date(2026, 6, 7))
        self.assertIn(date(2026, 6, 5), days)
        self.assertNotIn(date(2026, 6, 6), days)
        self.assertNotIn(date(2026, 6, 7), days)


class BarHealthTests(unittest.TestCase):
    def test_list_status_unknown(self) -> None:
        self.assertEqual(list_status(None), BarHealthStatus.UNKNOWN)

    def test_list_status_ok(self) -> None:
        meta = BarMeta(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 5),
            count=3,
        )
        self.assertEqual(
            list_status(meta, as_of=date(2026, 6, 5)),
            BarHealthStatus.OK,
        )

    def test_list_status_stale(self) -> None:
        meta = BarMeta(
            start=datetime(2026, 5, 1),
            end=datetime(2026, 5, 30),
            count=20,
        )
        self.assertEqual(
            list_status(meta, as_of=date(2026, 6, 5)),
            BarHealthStatus.STALE,
        )

    def test_status_label(self) -> None:
        self.assertEqual(status_label(BarHealthStatus.OK), "✅ 最新")
        self.assertEqual(status_label(BarHealthStatus.STALE), "⚠️ 过期")

    def test_merge_missing_days(self) -> None:
        gaps = merge_missing_days([date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 5)])
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0].missing_days, 2)
        self.assertEqual(gaps[1].missing_days, 1)

    def test_find_gaps(self) -> None:
        meta = BarMeta(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 5),
            count=3,
        )
        bar_dates = {date(2026, 6, 1), date(2026, 6, 5)}
        gaps = find_gaps(meta, bar_dates)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].start, date(2026, 6, 2))
        self.assertEqual(gaps[0].end, date(2026, 6, 4))

    def test_inspect_bar_gaps_marks_gaps(self) -> None:
        meta = BarMeta(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 5),
            count=2,
        )
        result = inspect_bar_gaps(meta, {date(2026, 6, 1), date(2026, 6, 5)}, as_of=date(2026, 6, 5))
        self.assertEqual(result.status, BarHealthStatus.GAPS)
        self.assertTrue(result.gaps)

    def test_format_gap_ranges(self) -> None:
        from vnpy_ashare.bar_health import GapRange

        text = format_gap_ranges(
            [
                GapRange(start=date(2026, 6, 2), end=date(2026, 6, 4), missing_days=3),
                GapRange(start=date(2026, 6, 5), end=date(2026, 6, 5), missing_days=1),
            ]
        )
        self.assertIn("2026-06-02~2026-06-04", text)
        self.assertIn("2026-06-05", text)


if __name__ == "__main__":
    unittest.main()
