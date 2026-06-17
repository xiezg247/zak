"""技术指标与概念服务单元测试。"""

from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from vnpy_ashare.domain.tech.indicators import calc_macd
from vnpy_ashare.services.stock.concept import build_concept_profile


class IndicatorsTests(unittest.TestCase):
    def test_calc_macd_length(self) -> None:
        closes = [float(i) for i in range(1, 41)]
        dif, dea, hist = calc_macd(closes)
        self.assertEqual(len(dif), len(closes))
        self.assertEqual(len(dea), len(closes))
        self.assertEqual(len(hist), len(closes))
        self.assertTrue(math.isnan(dif[0]))
        self.assertFalse(math.isnan(dif[-1]))


class ConceptServiceTests(unittest.TestCase):
    @patch("vnpy_ashare.services.stock.concept.fetch_stock_concepts")
    def test_build_concept_profile(self, mock_fetch) -> None:
        mock_fetch.return_value = [
            {"concept_id": "TS1", "concept_name": "人工智能"},
            {"concept_id": "TS2", "concept_name": "白酒"},
        ]
        profile = build_concept_profile("600519.SSE")
        self.assertEqual(len(profile.concepts), 2)
        self.assertEqual(profile.concepts[0]["concept_name"], "人工智能")


if __name__ == "__main__":
    unittest.main()
