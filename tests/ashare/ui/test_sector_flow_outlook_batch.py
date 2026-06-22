"""板块展望批量策略扫描测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.ui.sector_flow.outlook_batch import (
    OUTLOOK_BATCH_SCAN_MAX,
    coerce_sector_flow_rows,
    format_batch_scan_summary,
    prepare_batch_sector_scans,
)


def _sector(sector_id: str, name: str = "") -> SectorFlowRow:
    return SectorFlowRow(
        sector_id=sector_id,
        name=name or sector_id,
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=1.0,
        stock_count=10,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )


class OutlookBatchScanTests(unittest.TestCase):
    def test_prepare_empty_selection(self) -> None:
        queue, hint = prepare_batch_sector_scans([])
        self.assertEqual(queue, [])
        self.assertEqual(hint, "请先选择板块")

    def test_prepare_deduplicates(self) -> None:
        sectors = [_sector("a"), _sector("a"), _sector("b")]
        queue, hint = prepare_batch_sector_scans(sectors)
        self.assertEqual([item.sector_id for item in queue], ["a", "b"])
        self.assertIsNone(hint)

    def test_prepare_trims_to_max(self) -> None:
        sectors = [_sector(str(index)) for index in range(OUTLOOK_BATCH_SCAN_MAX + 2)]
        queue, hint = prepare_batch_sector_scans(sectors)
        self.assertEqual(len(queue), OUTLOOK_BATCH_SCAN_MAX)
        self.assertIn(str(OUTLOOK_BATCH_SCAN_MAX), hint or "")

    def test_coerce_tuple_payload(self) -> None:
        sector = _sector("a")
        self.assertEqual(coerce_sector_flow_rows((sector,)), [sector])

    def test_dedup_by_name_when_id_missing(self) -> None:
        row = SectorFlowRow(
            sector_id="",
            name="半导体",
            strength=1.0,
            change_pct=1.0,
            net_flow_yi=1.0,
            stock_count=10,
            up_ratio=0.5,
            flow_source="dc_industry",
            sector_kind="industry",
        )
        queue, hint = prepare_batch_sector_scans([row, row])
        self.assertEqual(len(queue), 1)
        self.assertIsNone(hint)

    def test_format_batch_summary(self) -> None:
        text = format_batch_scan_summary(
            total=3,
            succeeded=3,
            failed=0,
            aligned=2,
            diverged=1,
        )
        self.assertIn("3/3", text)
        self.assertIn("同向 2", text)
        self.assertIn("背离 1", text)


if __name__ == "__main__":
    unittest.main()
