"""本地页批量补全过期日 K、批量修复断层测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.bar_health import BarHealthStatus, BarMeta, GapRange
from vnpy_ashare.jobs.local_fill import (
    batch_fill_gap_daily_bars,
    batch_fill_stale_daily_bars,
    count_scannable_daily_items,
    count_stale_daily_items,
    fill_gap_ranges,
    fill_stale_daily_bar,
    select_stale_daily_items,
)
from vnpy_ashare.models import StockItem


class LocalFillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stale_meta = BarMeta(
            start=datetime(2026, 5, 1),
            end=datetime(2026, 5, 30),
            count=20,
        )
        self.ok_meta = BarMeta(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 5),
            count=3,
        )
        self.moutai = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        self.pingan = StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安银行")
        self.bar_meta = {
            (self.moutai.symbol, self.moutai.exchange): self.stale_meta,
            (self.pingan.symbol, self.pingan.exchange): self.ok_meta,
        }

    def test_select_stale_daily_items(self) -> None:
        items = select_stale_daily_items(
            [self.moutai, self.pingan],
            self.bar_meta,
            as_of=date(2026, 6, 5),
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].symbol, "600519")

    def test_count_stale_daily_items(self) -> None:
        self.assertEqual(
            count_stale_daily_items([self.moutai, self.pingan], self.bar_meta, as_of=date(2026, 6, 5)),
            1,
        )

    def test_count_scannable_daily_items(self) -> None:
        self.assertEqual(count_scannable_daily_items([self.moutai, self.pingan], self.bar_meta), 2)

    @patch("vnpy_ashare.jobs.local_fill.download_bars", return_value=3)
    def test_fill_stale_daily_bar(self, _mock_download) -> None:
        added = fill_stale_daily_bar(
            self.moutai,
            self.stale_meta,
            end=datetime(2026, 6, 5),
        )
        self.assertEqual(added, 3)

    @patch("vnpy_ashare.jobs.local_fill.download_bars")
    def test_batch_fill_stale_daily_bars(self, mock_download) -> None:
        mock_download.return_value = 2
        progress_labels: list[str] = []

        result = batch_fill_stale_daily_bars(
            [self.moutai],
            self.bar_meta,
            delay=0,
            end=datetime(2026, 6, 5),
            progress=lambda item: progress_labels.append(item.label),
        )

        self.assertEqual(result.success, 1)
        self.assertEqual(result.bars_added, 2)
        self.assertEqual(progress_labels, ["600519.上交所"])
        self.assertIn("成功 1/1", result.message)

    @patch("vnpy_ashare.jobs.local_fill.download_bars", return_value=2)
    def test_fill_gap_ranges(self, mock_download) -> None:
        gaps = [
            GapRange(start=date(2026, 5, 10), end=date(2026, 5, 12), missing_days=3),
        ]
        added = fill_gap_ranges(self.moutai, gaps, anchor_time=self.stale_meta.start)
        self.assertEqual(added, 2)
        mock_download.assert_called_once()

    @patch("vnpy_ashare.jobs.local_fill.inspect_item_gaps")
    @patch("vnpy_ashare.jobs.local_fill.download_bars", return_value=1)
    def test_batch_fill_gap_daily_bars(self, _mock_download, mock_inspect) -> None:
        from vnpy_ashare.bar_health import BarGapResult

        mock_inspect.side_effect = [
            BarGapResult(
                status=BarHealthStatus.GAPS,
                gaps=[GapRange(start=date(2026, 5, 10), end=date(2026, 5, 10), missing_days=1)],
                expected_days=20,
                actual_days=19,
            ),
            BarGapResult(
                status=BarHealthStatus.OK,
                gaps=[],
                expected_days=3,
                actual_days=3,
            ),
        ]
        phases: list[str] = []

        result = batch_fill_gap_daily_bars(
            [self.moutai, self.pingan],
            self.bar_meta,
            delay=0,
            progress=lambda item: phases.append(item.phase),
        )

        self.assertEqual(result.scanned, 2)
        self.assertEqual(result.with_gaps, 1)
        self.assertEqual(result.success, 1)
        self.assertEqual(result.gap_ranges_fixed, 1)
        self.assertIn("scan", phases)
        self.assertIn("fix", phases)
        self.assertIn("成功 1/1", result.message)


if __name__ == "__main__":
    unittest.main()
