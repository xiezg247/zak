"""雷达板块·主线 → 板块资金联动数据。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar.radar_sector import load_sector_theme


class RadarSectorFlowLinkTests(unittest.TestCase):
    def test_sector_names_on_leaders(self) -> None:
        hits = [
            mock.Mock(
                row={
                    "vt_symbol": "600000.SSE",
                    "industry": "银行",
                    "change_pct": 2.0,
                    "amount": 1e9,
                }
            ),
            mock.Mock(
                row={
                    "vt_symbol": "600016.SSE",
                    "industry": "白酒",
                    "change_pct": 1.0,
                    "amount": 1e9,
                }
            ),
        ]
        with mock.patch(
            "vnpy_ashare.quotes.radar.radar_sector.run_sector_strength",
            return_value=(hits, 100),
        ):
            data = load_sector_theme(RADAR_CARD_BY_ID["sector_theme"], variant="leaders")
        self.assertEqual(data.sector_names[:2], ("银行", "白酒"))


if __name__ == "__main__":
    unittest.main()
