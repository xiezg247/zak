"""板块资金历史落库测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vnpy_ashare.domain.sector_flow import SectorFlowRow
from vnpy_ashare.storage.repositories.sector_flow_history import load_sector_flow_history, upsert_sector_flow_day


class SectorFlowHistoryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "test.db"
        self._patch = mock.patch(
            "vnpy_common.paths.get_app_db_path",
            return_value=self._db_path,
        )
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()

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


class SectorFlowHistoryMergeTests(unittest.TestCase):
    def test_merge_prefers_local_on_same_date(self) -> None:
        from vnpy_ashare.domain.sector_flow import SectorFlowHistoryPoint
        from vnpy_ashare.storage.repositories.sector_flow_history import merge_sector_flow_history

        local = [SectorFlowHistoryPoint("20240925", 10.0)]
        remote = [
            SectorFlowHistoryPoint("20240925", 9.0),
            SectorFlowHistoryPoint("20240926", -1.0),
        ]
        merged = merge_sector_flow_history(local, remote, limit=5)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].net_flow_yi, 10.0)
        self.assertEqual(merged[1].trade_date, "20240926")


if __name__ == "__main__":
    unittest.main()
