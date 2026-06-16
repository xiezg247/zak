"""板块资金聚合测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.sector_flow import SectorFlowRow
from vnpy_ashare.services.sector_flow_service import (
    aggregate_sector_rows,
    build_official_snapshot,
    build_sector_snapshot,
    diagnose_sector_flow_empty,
    rows_from_dc_moneyflow,
    rows_from_ths_concept_moneyflow,
    split_sector_display_rows,
)


class SectorFlowAggregatorTests(unittest.TestCase):
    def test_aggregate_by_industry(self) -> None:
        rows = [
            {
                "vt_symbol": "600000.SSE",
                "change_pct": 2.0,
                "amount": 1e9,
                "net_mf_amount": 1000,
                "industry": "银行",
            },
            {
                "vt_symbol": "600016.SSE",
                "change_pct": 1.0,
                "amount": 8e8,
                "net_mf_amount": 500,
                "industry": "银行",
            },
            {
                "vt_symbol": "601398.SSE",
                "change_pct": 0.5,
                "amount": 6e8,
                "net_mf_amount": 300,
                "industry": "银行",
            },
            {
                "vt_symbol": "600519.SSE",
                "change_pct": -1.0,
                "amount": 2e9,
                "net_mf_amount": -800,
                "industry": "白酒",
            },
            {
                "vt_symbol": "000858.SZSE",
                "change_pct": -0.5,
                "amount": 5e8,
                "net_mf_amount": -200,
                "industry": "白酒",
            },
            {
                "vt_symbol": "000001.SZSE",
                "change_pct": 0.2,
                "amount": 3e8,
                "net_mf_amount": 0,
                "industry": "白酒",
            },
        ]
        # attach_industry will skip if no tushare map - rows already have industry

        with mock.patch(
            "vnpy_ashare.services.sector_flow_service.attach_industry",
            side_effect=lambda r, industry_map=None: r,
        ):
            result = aggregate_sector_rows(rows)
        self.assertEqual(len(result), 2)
        bank = next(item for item in result if item.name == "银行")
        self.assertGreater(bank.net_flow_yi, 0)
        self.assertEqual(bank.flow_source, "tushare")

    def test_build_snapshot_top_in_out(self) -> None:
        rows = [
            {"vt_symbol": "a.SSE", "change_pct": 3, "amount": 1e9, "net_mf_amount": 20000, "industry": "A"},
            {"vt_symbol": "b.SSE", "change_pct": 2, "amount": 1e9, "net_mf_amount": 10000, "industry": "A"},
            {"vt_symbol": "c.SSE", "change_pct": 1, "amount": 1e9, "net_mf_amount": 5000, "industry": "A"},
            {"vt_symbol": "d.SSE", "change_pct": -2, "amount": 1e9, "net_mf_amount": -30000, "industry": "B"},
            {"vt_symbol": "e.SSE", "change_pct": -1, "amount": 1e9, "net_mf_amount": -10000, "industry": "B"},
            {"vt_symbol": "f.SSE", "change_pct": -0.5, "amount": 1e9, "net_mf_amount": -5000, "industry": "B"},
        ]
        with mock.patch(
            "vnpy_ashare.services.sector_flow_service.attach_industry",
            side_effect=lambda r, industry_map=None: r,
        ):
            snap = build_sector_snapshot(rows, updated_at="12:00")
        self.assertEqual(snap.top_inflow_name, "A")
        self.assertEqual(snap.top_outflow_name, "B")
        self.assertGreater(len(snap.inflow_rows), 0)
        self.assertGreater(len(snap.outflow_rows), 0)

    def test_split_keeps_outflow_when_many_inflows(self) -> None:
        rows = [
            SectorFlowRow(
                sector_id=f"IN{i}",
                name=f"IN{i}",
                strength=10.0,
                change_pct=1.0,
                net_flow_yi=float(i + 1),
                stock_count=3,
                up_ratio=0.5,
                flow_source="tushare",
            )
            for i in range(30)
        ] + [
            SectorFlowRow(
                sector_id="OUT1",
                name="OUT1",
                strength=1.0,
                change_pct=-2.0,
                net_flow_yi=-5.0,
                stock_count=3,
                up_ratio=0.2,
                flow_source="tushare",
            )
        ]
        inflow, outflow = split_sector_display_rows(rows)
        self.assertEqual(len(inflow), 24)
        self.assertEqual(len(outflow), 1)
        self.assertEqual(outflow[0].name, "OUT1")


class SectorFlowEmptyHintTests(unittest.TestCase):
    def test_diagnose_no_industry_map(self) -> None:
        rows = [{"vt_symbol": "600000.SSE", "change_pct": 1.0, "amount": 1e9}]
        with mock.patch(
            "vnpy_ashare.services.sector_flow_service.attach_industry",
            return_value=[],
        ):
            hint = diagnose_sector_flow_empty(rows, raw_total=100)
        self.assertIn("行业", hint)
        self.assertIn("TUSHARE", hint)

    def test_diagnose_min_stocks(self) -> None:
        rows = [
            {"vt_symbol": "a.SSE", "industry": "X", "change_pct": 1},
            {"vt_symbol": "b.SSE", "industry": "X", "change_pct": 2},
        ]
        with mock.patch(
            "vnpy_ashare.services.sector_flow_service.attach_industry",
            side_effect=lambda r, industry_map=None: r,
        ):
            hint = diagnose_sector_flow_empty(rows, raw_total=2)
        self.assertIn("3", hint)

    def test_snapshot_empty_hint(self) -> None:
        rows = [{"vt_symbol": "a.SSE", "industry": "X", "change_pct": 1}]
        with mock.patch(
            "vnpy_ashare.services.sector_flow_service.attach_industry",
            side_effect=lambda r, industry_map=None: r,
        ):
            snap = build_sector_snapshot(rows, updated_at="12:00")
        self.assertEqual(snap.rows, ())
        self.assertTrue(snap.empty_hint)


class SectorFlowOfficialRowsTests(unittest.TestCase):
    def test_rows_from_dc_moneyflow(self) -> None:
        rows = [
            {
                "ts_code": "BK0001",
                "name": "互联网服务",
                "pct_change": 6.28,
                "net_amount": 3_056_382_208.0,
                "net_amount_rate": 3.93,
                "leader_stock": "三六五网",
            },
            {
                "ts_code": "BK0002",
                "name": "银行",
                "pct_change": -0.33,
                "net_amount": -2_340_180_224.0,
                "net_amount_rate": -6.41,
                "leader_stock": "招商银行",
            },
        ]
        result = rows_from_dc_moneyflow(rows, sector_kind="industry", flow_source="dc_industry")
        self.assertEqual(len(result), 2)
        leader = next(item for item in result if item.name == "互联网服务")
        self.assertAlmostEqual(leader.net_flow_yi, 30.56, places=1)
        self.assertEqual(leader.leader_stock, "三六五网")
        self.assertEqual(leader.flow_source, "dc_industry")

    def test_rows_from_ths_concept_moneyflow(self) -> None:
        rows = [
            {
                "ts_code": "885748.TI",
                "name": "可燃冰",
                "pct_change": 4.76,
                "net_amount": 1.0,
                "company_num": 12,
                "leader_stock": "海默科技",
                "leader_change_pct": 4.76,
            }
        ]
        result = rows_from_ths_concept_moneyflow(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "可燃冰")
        self.assertEqual(result[0].sector_kind, "concept")
        self.assertEqual(result[0].stock_count, 12)

    def test_build_official_snapshot(self) -> None:
        row = SectorFlowRow(
            sector_id="BK1",
            name="测试",
            strength=5.0,
            change_pct=3.0,
            net_flow_yi=10.0,
            stock_count=0,
            up_ratio=0.0,
            flow_source="dc_industry",
            sector_kind="industry",
        )
        snap = build_official_snapshot(
            [row],
            trade_date="20240927",
            sector_kind="industry",
            data_mode="official_dc",
        )
        self.assertEqual(snap.data_mode, "official_dc")
        self.assertIn("日终", snap.updated_at or "")


if __name__ == "__main__":
    unittest.main()
