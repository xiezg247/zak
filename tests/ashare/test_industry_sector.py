"""申万行业板块统一口径测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.integrations.tushare.sw_industry import (
    build_sw_l2_board_definitions,
    classify_rows_to_l2_index_map,
)
from vnpy_ashare.services.industry_sector import (
    build_sw_industry_rows_from_dc,
    normalize_sw_industry_sector_rows,
    overlay_dc_moneyflow_on_sw_rows,
)
from vnpy_ashare.services.sector_flow import aggregate_sector_rows


class SwIndustryBoardTests(unittest.TestCase):
    def test_classify_rows_to_l2_index_map(self) -> None:
        rows = [
            {"industry_name": "工业金属", "index_code": "801050.SI"},
            {"industry_name": "白酒", "index_code": "801120.SI"},
        ]
        self.assertEqual(classify_rows_to_l2_index_map(rows)["工业金属"], "801050.SI")

    def test_build_sw_l2_board_definitions(self) -> None:
        classify = [{"industry_name": "工业金属", "index_code": "801050.SI"}]
        members = [
            {"ts_code": "600362.SH", "l2_name": "工业金属", "l1_name": "有色金属", "out_date": ""},
            {"ts_code": "600519.SH", "l2_name": "白酒", "l1_name": "食品饮料", "out_date": ""},
        ]
        boards = build_sw_l2_board_definitions(
            classify_rows=classify,
            member_rows=members,
            l2_to_l1={"工业金属": "有色金属"},
        )
        self.assertEqual(boards[0]["index_code"], "801050.SI")
        self.assertEqual(boards[0]["member_count"], 1)


class IndustrySectorUnifiedTests(unittest.TestCase):
    def test_normalize_dc_rows_to_sw(self) -> None:
        rows = [
            SectorFlowRow(
                sector_id="BK001",
                name="工业金属",
                strength=1.0,
                change_pct=2.0,
                net_flow_yi=3.0,
                stock_count=0,
                up_ratio=0.0,
                flow_source="dc_industry",
                sector_kind="industry",
            ),
            SectorFlowRow(
                sector_id="BK999",
                name="非申万行业",
                strength=1.0,
                change_pct=1.0,
                net_flow_yi=1.0,
                stock_count=0,
                up_ratio=0.0,
                flow_source="dc_industry",
                sector_kind="industry",
            ),
        ]
        with patch(
            "vnpy_ashare.services.industry_sector.fetch_sw_l2_index_map",
            return_value={"工业金属": "801050.SI"},
        ):
            normalized = normalize_sw_industry_sector_rows(rows)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0].sector_id, "801050.SI")
        self.assertEqual(normalized[0].flow_source, "sw_dc")

    def test_build_sw_industry_rows_from_dc(self) -> None:
        dc_rows = [
            {
                "ts_code": "BK001",
                "name": "工业金属",
                "pct_change": 1.5,
                "net_amount": 1_000_000_000.0,
                "net_amount_rate": 1.0,
                "leader_stock": "江西铜业",
            }
        ]
        with patch(
            "vnpy_ashare.services.industry_sector.fetch_sw_l2_index_map",
            return_value={"工业金属": "801050.SI"},
        ):
            result = build_sw_industry_rows_from_dc(dc_rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].sector_id, "801050.SI")
        self.assertEqual(result[0].leader_stock, "江西铜业")

    def test_aggregate_uses_sw_index_code(self) -> None:
        rows = [
            {"vt_symbol": "600362.SSE", "change_pct": 2.0, "amount": 1e9, "net_mf_amount": 1000, "industry": "工业金属"},
            {"vt_symbol": "601899.SSE", "change_pct": 1.0, "amount": 8e8, "net_mf_amount": 500, "industry": "工业金属"},
            {"vt_symbol": "600111.SSE", "change_pct": 0.5, "amount": 6e8, "net_mf_amount": 300, "industry": "工业金属"},
        ]
        with (
            patch(
                "vnpy_ashare.services.sector_flow.attach_industry",
                side_effect=lambda r, industry_map=None: r,
            ),
            patch(
                "vnpy_ashare.services.sector_flow.fetch_sw_l2_index_map",
                return_value={"工业金属": "801050.SI"},
            ),
        ):
            result = aggregate_sector_rows(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].sector_id, "801050.SI")
        self.assertEqual(result[0].name, "工业金属")

    def test_overlay_dc_moneyflow(self) -> None:
        sw_rows = [
            SectorFlowRow(
                sector_id="801050.SI",
                name="工业金属",
                strength=5.0,
                change_pct=1.0,
                net_flow_yi=0.5,
                stock_count=10,
                up_ratio=0.6,
                flow_source="proxy",
                sector_kind="industry",
            )
        ]
        dc_rows = [
            {
                "ts_code": "BK001",
                "name": "工业金属",
                "pct_change": 2.0,
                "net_amount": 2_000_000_000.0,
                "net_amount_rate": 1.5,
                "leader_stock": "江西铜业",
            }
        ]
        with patch(
            "vnpy_ashare.services.industry_sector.fetch_sw_l2_index_map",
            return_value={"工业金属": "801050.SI"},
        ):
            merged = overlay_dc_moneyflow_on_sw_rows(sw_rows, dc_rows)
        self.assertEqual(merged[0].flow_source, "sw_dc")
        self.assertAlmostEqual(merged[0].net_flow_yi, 20.0, places=1)
        self.assertEqual(merged[0].leader_stock, "江西铜业")


if __name__ == "__main__":
    unittest.main()
