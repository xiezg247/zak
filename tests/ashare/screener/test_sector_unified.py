"""行业/概念双轴附加测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields, compute_sector_distribution


class AttachSectorFieldsTest(unittest.TestCase):
    def test_attach_both_axes(self) -> None:
        rows = [
            {"vt_symbol": "600000.SSE", "change_pct": 5.0},
            {"vt_symbol": "600519.SSE", "change_pct": 3.0},
        ]
        industry_map = {"600000.SH": "银行", "600519.SH": "白酒"}
        concept_map = {"600000.SSE": "人工智能", "600519.SSE": "消费"}
        enriched, hot = attach_sector_fields(
            rows,
            industry_map=industry_map,
            vt_to_concept=concept_map,
        )
        self.assertEqual(len(enriched), 2)
        self.assertEqual(enriched[0]["industry"], "银行")
        self.assertEqual(enriched[0]["concept"], "人工智能")
        self.assertIn("人工智能", hot)

    def test_concept_distribution(self) -> None:
        rows = [
            {"concept": "人工智能", "change_pct": 8.0},
            {"concept": "人工智能", "change_pct": 6.0},
            {"concept": "新能源", "change_pct": 2.0},
            {"concept": "新能源", "change_pct": 1.0},
        ]
        stats = compute_sector_distribution(rows, sector_field="concept", min_stocks=2)
        self.assertGreaterEqual(len(stats), 1)
        self.assertEqual(stats[0]["concept"], "人工智能")
