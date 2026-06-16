"""Tushare 板块资金历史回填测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.sector_flow import SectorFlowRow
from vnpy_ashare.integrations.tushare.sector_moneyflow import fetch_sector_flow_history_from_tushare


class SectorFlowTushareHistoryTests(unittest.TestCase):
    def test_fetch_dc_industry_history(self) -> None:
        sector = SectorFlowRow(
            sector_id="BK001",
            name="互联网服务",
            strength=1,
            change_pct=1,
            net_flow_yi=1,
            stock_count=0,
            up_ratio=0,
            flow_source="dc_industry",
            sector_kind="industry",
        )

        def fake_dc(*, trade_date: str, content_type: str | None = None):
            if trade_date == "20240927":
                return (
                    [
                        {
                            "trade_date": "20240927",
                            "ts_code": "BK001",
                            "name": "互联网服务",
                            "net_amount": 2_000_000_000.0,
                        }
                    ],
                    trade_date,
                )
            if trade_date == "20240926":
                return (
                    [
                        {
                            "trade_date": "20240926",
                            "ts_code": "BK001",
                            "name": "互联网服务",
                            "net_amount": -500_000_000.0,
                        }
                    ],
                    trade_date,
                )
            return [], trade_date

        with (
            mock.patch(
                "vnpy_ashare.integrations.tushare.sector_moneyflow.recent_trading_date_strs",
                return_value=["20240927", "20240926", "20240925"],
            ),
            mock.patch(
                "vnpy_ashare.integrations.tushare.sector_moneyflow.fetch_moneyflow_ind_dc",
                side_effect=fake_dc,
            ),
        ):
            points = fetch_sector_flow_history_from_tushare(sector, limit=2)

        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].trade_date, "20240926")
        self.assertAlmostEqual(points[0].net_flow_yi, -5.0)
        self.assertAlmostEqual(points[1].net_flow_yi, 20.0)

    def test_fetch_ths_concept_history(self) -> None:
        sector = SectorFlowRow(
            sector_id="885748.TI",
            name="可燃冰",
            strength=1,
            change_pct=1,
            net_flow_yi=1,
            stock_count=12,
            up_ratio=0,
            flow_source="ths_concept",
            sector_kind="concept",
        )

        with (
            mock.patch(
                "vnpy_ashare.integrations.tushare.sector_moneyflow.recent_trading_date_strs",
                return_value=["20250320"],
            ),
            mock.patch(
                "vnpy_ashare.integrations.tushare.sector_moneyflow.fetch_moneyflow_cnt_ths",
                return_value=(
                    [
                        {
                            "trade_date": "20250320",
                            "ts_code": "885748.TI",
                            "name": "可燃冰",
                            "net_amount": 1.0,
                        }
                    ],
                    "20250320",
                ),
            ),
        ):
            points = fetch_sector_flow_history_from_tushare(sector, limit=5)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].trade_date, "20250320")
        self.assertAlmostEqual(points[0].net_flow_yi, 1.0)


if __name__ == "__main__":
    unittest.main()
