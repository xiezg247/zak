"""板块近 N 日轮动聚合测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.services.sector_flow_rotation import (
    build_rotation_rows,
    build_rotation_snapshot,
    classify_flow_pattern,
    filter_rotation_rows,
    format_rotation_ai_lines,
)
from vnpy_ashare.storage.repositories.sector_flow_history import upsert_sector_flow_day


def _sector_row(sector_id: str, name: str, net_flow_yi: float) -> SectorFlowRow:
    return SectorFlowRow(
        sector_id=sector_id,
        name=name,
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=net_flow_yi,
        stock_count=3,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )


class SectorFlowRotationLogicTests(unittest.TestCase):
    def test_classify_continuous_inflow(self) -> None:
        from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint

        values = [1.0] * 10 + [5.0] * 5
        points = tuple(SectorFlowHistoryPoint(trade_date=f"202409{i:02d}", net_flow_yi=values[i - 1]) for i in range(1, 16))
        self.assertEqual(classify_flow_pattern(points), "持续流入")

    def test_classify_in_then_out(self) -> None:
        from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint

        values = [2.0] * 7 + [-2.0] * 8
        points = tuple(SectorFlowHistoryPoint(trade_date=f"202409{i:02d}", net_flow_yi=values[i - 1]) for i in range(1, 16))
        self.assertEqual(classify_flow_pattern(points), "先入后出")

    def test_build_rotation_rows_sort_and_metrics(self) -> None:
        snapshot = SectorFlowSnapshot(
            rows=(),
            inflow_rows=(_sector_row("A", "A板块", 10.0), _sector_row("B", "B板块", 5.0)),
            outflow_rows=(_sector_row("C", "C板块", -3.0),),
            sector_kind="industry",
            data_mode="official_dc",
        )
        trade_dates = tuple(f"202409{i:02d}" for i in range(11, 26))
        matrix = {
            "A": {date: 2.0 for date in trade_dates},
            "B": {date: 1.0 for date in trade_dates},
            "C": {date: -1.0 for date in trade_dates},
        }
        rows = build_rotation_rows(snapshot, matrix, trade_dates=trade_dates)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].sector.name, "A板块")
        self.assertAlmostEqual(rows[0].cumulative_net_yi, 30.0)
        self.assertEqual(rows[0].positive_days, 15)

    def test_filter_rotation_rows(self) -> None:
        from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint, SectorFlowRotationRow

        rows = (
            SectorFlowRotationRow(
                sector=_sector_row("A", "A", 1.0),
                points=(SectorFlowHistoryPoint(trade_date="20240901", net_flow_yi=1.0),),
                cumulative_net_yi=1.0,
                positive_days=1,
                flow_pattern="持续流入",
                momentum_delta=1.0,
            ),
            SectorFlowRotationRow(
                sector=_sector_row("B", "B", -1.0),
                points=(SectorFlowHistoryPoint(trade_date="20240901", net_flow_yi=-1.0),),
                cumulative_net_yi=-1.0,
                positive_days=0,
                flow_pattern="持续流出",
                momentum_delta=-1.0,
            ),
        )
        filtered = filter_rotation_rows(rows, "持续流入")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].sector.name, "A")

    def test_format_rotation_ai_lines(self) -> None:
        from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint, SectorFlowRotationRow, SectorFlowRotationSnapshot

        rotation = SectorFlowRotationSnapshot(
            trade_dates=("20240901",),
            rows=(
                SectorFlowRotationRow(
                    sector=_sector_row("A", "半导体", 10.0),
                    points=(SectorFlowHistoryPoint(trade_date="20240901", net_flow_yi=10.0),),
                    cumulative_net_yi=10.0,
                    positive_days=1,
                    flow_pattern="持续流入",
                    momentum_delta=2.0,
                    rank_delta=3,
                ),
            ),
            sector_kind="industry",
        )
        lines = format_rotation_ai_lines(rotation, limit=3)
        self.assertTrue(any("近15日行业板块资金轮动" in line for line in lines))
        self.assertTrue(any("半导体" in line for line in lines))


class SectorFlowRotationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "test.db"
        self._patch = mock.patch(
            "vnpy_ashare.storage.connection._db_path",
            return_value=self._db_path,
        )
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()

    def test_build_rotation_snapshot_from_local_db(self) -> None:
        trade_dates = [f"202409{i:02d}" for i in range(11, 26)]
        for index, trade_date in enumerate(trade_dates):
            upsert_sector_flow_day(
                trade_date,
                "industry",
                [_sector_row("801001.SI", "半导体", 2.0 if index < 10 else 5.0)],
            )
        snapshot = SectorFlowSnapshot(
            rows=(),
            inflow_rows=(_sector_row("801001.SI", "半导体", 10.0),),
            outflow_rows=(),
            sector_kind="industry",
            data_mode="official_dc",
            trade_date=trade_dates[-1],
        )
        with mock.patch(
            "vnpy_ashare.services.sector_flow_rotation.rotation_trade_dates",
            return_value=tuple(trade_dates),
        ):
            rotation = build_rotation_snapshot(snapshot)
        self.assertEqual(len(rotation.trade_dates), 15)
        self.assertEqual(len(rotation.rows), 1)
        self.assertGreater(rotation.rows[0].cumulative_net_yi, 0)


if __name__ == "__main__":
    unittest.main()
