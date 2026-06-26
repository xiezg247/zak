"""板块资金历史落库测试。"""

from __future__ import annotations

import unittest

from tests.ashare.pg_unittest import PgAppStorageTestCase
from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.storage.repositories.sector_flow_history import load_sector_flow_history, upsert_sector_flow_day


class SectorFlowHistoryRepositoryTests(PgAppStorageTestCase):
    def test_upsert_and_load_history(self) -> None:
        row = SectorFlowRow(
            sector_id="BK001",
            name="互联网",
            strength=1,
            change_pct=2,
            net_flow_yi=10.5,
            stock_count=0,
            up_ratio=0,
            flow_source="dc_industry",
            sector_kind="industry",
        )
        upsert_sector_flow_day("20240925", "industry", [row])
        upsert_sector_flow_day(
            "20240926",
            "industry",
            [
                SectorFlowRow(
                    sector_id="BK001",
                    name="互联网",
                    strength=1,
                    change_pct=1,
                    net_flow_yi=-3.2,
                    stock_count=0,
                    up_ratio=0,
                    flow_source="dc_industry",
                    sector_kind="industry",
                )
            ],
        )
        history = load_sector_flow_history(sector_id="BK001", sector_kind="industry", limit=5)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].trade_date, "20240925")
        self.assertAlmostEqual(history[1].net_flow_yi, -3.2)

    def test_load_sector_flow_matrix(self) -> None:
        from vnpy_ashare.storage.repositories.sector_flow_history import load_sector_flow_matrix

        row_a = SectorFlowRow(
            sector_id="BK001",
            name="互联网",
            strength=1,
            change_pct=2,
            net_flow_yi=10.5,
            stock_count=0,
            up_ratio=0,
            flow_source="dc_industry",
            sector_kind="industry",
        )
        row_b = SectorFlowRow(
            sector_id="BK002",
            name="银行",
            strength=1,
            change_pct=-1,
            net_flow_yi=-2.0,
            stock_count=0,
            up_ratio=0,
            flow_source="dc_industry",
            sector_kind="industry",
        )
        upsert_sector_flow_day("20240925", "industry", [row_a])
        upsert_sector_flow_day("20240926", "industry", [row_a, row_b])
        matrix = load_sector_flow_matrix(
            sector_kind="industry",
            trade_dates=["20240925", "20240926"],
            sector_ids=["BK001", "BK002"],
        )
        self.assertAlmostEqual(matrix["BK001"]["20240925"], 10.5)
        self.assertAlmostEqual(matrix["BK002"]["20240926"], -2.0)
        self.assertNotIn("20240925", matrix.get("BK002", {}))


class SectorFlowHistoryMergeTests(unittest.TestCase):
    def test_merge_prefers_local_on_same_date(self) -> None:
        from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint
        from vnpy_ashare.storage.repositories.sector_flow_history import merge_sector_flow_history

        local = [SectorFlowHistoryPoint(trade_date="20240925", net_flow_yi=10.0)]
        remote = [
            SectorFlowHistoryPoint(trade_date="20240925", net_flow_yi=9.0),
            SectorFlowHistoryPoint(trade_date="20240926", net_flow_yi=-1.0),
        ]
        merged = merge_sector_flow_history(local, remote, limit=5)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].net_flow_yi, 10.0)
        self.assertEqual(merged[1].trade_date, "20240926")


if __name__ == "__main__":
    unittest.main()
