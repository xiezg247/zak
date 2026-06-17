"""本地 K 线健康状态测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.bar_health import (
    UNIFIED_BAR_START,
    BarHealthStatus,
    BarMeta,
    bar_meta_from_overview,
    clip_bars_from_unified_start,
    effective_bar_start,
    find_gaps,
    format_gap_ranges,
    gap_scan_range,
    inspect_bar_gaps,
    list_status,
    merge_missing_days,
    status_label,
)
from vnpy_ashare.data.bar_store import PeriodBarOverview
from vnpy_ashare.domain.time.calendar import is_trading_day, last_trading_day, trading_days_between


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
    def test_effective_bar_start_before_unified(self) -> None:
        self.assertEqual(effective_bar_start(datetime(2019, 5, 1)), UNIFIED_BAR_START)

    def test_effective_bar_start_after_unified(self) -> None:
        actual = datetime(2023, 6, 1)
        self.assertEqual(effective_bar_start(actual), actual)

    def test_bar_meta_from_overview(self) -> None:
        row = PeriodBarOverview(
            symbol="600519",
            exchange=Exchange.SSE,
            period="daily",
            start=datetime(2023, 6, 1),
            end=datetime(2026, 6, 5),
            count=500,
        )
        meta = bar_meta_from_overview(row)
        self.assertEqual(meta.start, datetime(2023, 6, 1))

    def test_bar_meta_from_overview_clamps_early_start(self) -> None:
        row = PeriodBarOverview(
            symbol="600519",
            exchange=Exchange.SSE,
            period="daily",
            start=datetime(2019, 1, 2),
            end=datetime(2026, 6, 5),
            count=500,
        )
        meta = bar_meta_from_overview(row)
        self.assertEqual(meta.start, UNIFIED_BAR_START)

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

    def test_gap_scan_ignores_pre_unified_dates(self) -> None:
        meta = BarMeta(
            start=UNIFIED_BAR_START,
            end=datetime(2026, 6, 5),
            count=500,
        )
        listing_start = date(2023, 6, 1)
        bar_dates = set(trading_days_between(listing_start, date(2026, 6, 5)))
        scan_start, scan_end = gap_scan_range(meta, bar_dates)
        self.assertEqual(scan_start, listing_start)
        self.assertEqual(scan_end, date(2026, 6, 5))
        result = inspect_bar_gaps(meta, bar_dates, as_of=date(2026, 6, 5))
        self.assertEqual(result.status, BarHealthStatus.OK)
        self.assertEqual(result.gaps, [])

    def test_clip_bars_from_unified_start(self) -> None:
        from vnpy.trader.constant import Interval
        from vnpy.trader.object import BarData

        bars = [
            BarData(
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=datetime(2019, 12, 31),
                interval=Interval.DAILY,
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                volume=1,
                gateway_name="DB",
            ),
            BarData(
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=datetime(2020, 1, 2),
                interval=Interval.DAILY,
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                volume=1,
                gateway_name="DB",
            ),
        ]
        clipped = clip_bars_from_unified_start(bars)
        self.assertEqual(len(clipped), 1)
        self.assertEqual(clipped[0].datetime, datetime(2020, 1, 2))

    def test_format_gap_ranges(self) -> None:
        from vnpy_ashare.data.bar_health import GapRange

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
