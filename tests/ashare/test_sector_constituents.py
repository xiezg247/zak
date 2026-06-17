"""板块成分与量价背离测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.sector_flow import SectorFlowRow
from vnpy_ashare.services.sector_constituents import compute_divergence_rows, load_sector_leaders
from vnpy_ashare.services.sector_flow import build_official_snapshot


class SectorDivergenceTests(unittest.TestCase):
    def test_compute_divergence_rows(self) -> None:
        rows = [
            SectorFlowRow(
                sector_id="A",
                name="A",
                strength=5,
                change_pct=2.0,
                net_flow_yi=-1.0,
                stock_count=3,
                up_ratio=0.5,
                flow_source="tushare",
            ),
            SectorFlowRow(
                sector_id="B",
                name="B",
                strength=3,
                change_pct=-1.5,
                net_flow_yi=2.0,
                stock_count=3,
                up_ratio=0.3,
                flow_source="tushare",
            ),
            SectorFlowRow(
                sector_id="C",
                name="C",
                strength=4,
                change_pct=1.0,
                net_flow_yi=0.5,
                stock_count=3,
                up_ratio=0.6,
                flow_source="tushare",
            ),
        ]
        hits = compute_divergence_rows(rows)
        self.assertEqual(len(hits), 2)
        kinds = {item.divergence_kind for item in hits}
        self.assertEqual(kinds, {"价涨流出", "价跌流入"})

    def test_snapshot_includes_divergence(self) -> None:
        row = SectorFlowRow(
            sector_id="A",
            name="A",
            strength=5,
            change_pct=3.0,
            net_flow_yi=-2.0,
            stock_count=0,
            up_ratio=0.0,
            flow_source="dc_industry",
        )
        snap = build_official_snapshot(
            [row],
            trade_date="20240927",
            sector_kind="industry",
            data_mode="official_dc",
        )
        self.assertEqual(len(snap.divergence_rows), 1)
        self.assertEqual(snap.divergence_rows[0].divergence_kind, "价涨流出")


class SectorLeadersTests(unittest.TestCase):
    def test_load_industry_leaders(self) -> None:
        sector = SectorFlowRow(
            sector_id="银行",
            name="银行",
            strength=1,
            change_pct=1,
            net_flow_yi=1,
            stock_count=2,
            up_ratio=0.5,
            flow_source="tushare",
            sector_kind="industry",
        )
        quotes = [
            {"vt_symbol": "600000.SSE", "name": "浦发银行", "change_pct": 2.0, "net_mf_amount": 1000, "industry": "银行"},
            {"vt_symbol": "600016.SSE", "name": "民生银行", "change_pct": 1.0, "net_mf_amount": 500, "industry": "银行"},
            {"vt_symbol": "600519.SSE", "name": "茅台", "change_pct": 3.0, "net_mf_amount": 9000, "industry": "白酒"},
        ]
        with mock.patch(
            "vnpy_ashare.services.sector_constituents.attach_industry",
            side_effect=lambda rows, industry_map=None: rows,
        ):
            leaders = load_sector_leaders(sector, quotes, limit=2)
        self.assertEqual(len(leaders), 2)
        self.assertEqual(leaders[0].name, "浦发银行")

    def test_fallback_to_official_leader_name(self) -> None:
        sector = SectorFlowRow(
            sector_id="885748.TI",
            name="可燃冰",
            strength=1,
            change_pct=4.0,
            net_flow_yi=1.0,
            stock_count=12,
            up_ratio=0.0,
            flow_source="ths_concept",
            sector_kind="concept",
            leader_stock="海默科技",
        )
        with mock.patch(
            "vnpy_ashare.services.sector_constituents._resolve_concept_vt_symbols",
            return_value=set(),
        ):
            leaders = load_sector_leaders(sector, [], limit=5)
        self.assertEqual(len(leaders), 1)
        self.assertEqual(leaders[0].name, "海默科技")


if __name__ == "__main__":
    unittest.main()
