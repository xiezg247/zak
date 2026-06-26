"""板块资金概览：桶对齐与快照构建。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

from tests.ashare.pg_unittest import PgAppStorageTestCase
from vnpy_ashare.domain.market.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.domain.time.market_hours import (
    AFTERNOON_CLOSE_MIN,
    CHINA_TZ,
    MORNING_CLOSE_MIN,
    MORNING_OPEN_MIN,
)
from vnpy_ashare.services.sector_flow_overview import (
    build_overview_snapshot,
    intraday_bucket_time,
    record_intraday_overview_sample,
)
from vnpy_ashare.storage.repositories.sector_flow_intraday import (
    load_intraday_records,
    upsert_intraday_samples,
)


def _row(sector_id: str, name: str, net_flow_yi: float, *, change_pct: float = 0.0) -> SectorFlowRow:
    return SectorFlowRow(
        sector_id=sector_id,
        name=name,
        strength=1.0,
        change_pct=change_pct,
        net_flow_yi=net_flow_yi,
        stock_count=10,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )


def _snapshot(
    rows: list[SectorFlowRow],
    *,
    data_mode: str = "official_dc",
    trade_date: str = "2024-06-20",
) -> SectorFlowSnapshot:
    inflow = sorted([row for row in rows if row.net_flow_yi > 0], key=lambda item: item.net_flow_yi, reverse=True)
    outflow = sorted([row for row in rows if row.net_flow_yi < 0], key=lambda item: item.net_flow_yi)
    top_inflow = inflow[0] if inflow else None
    top_outflow = outflow[0] if outflow else None
    return SectorFlowSnapshot(
        rows=tuple(rows),
        inflow_rows=tuple(inflow),
        outflow_rows=tuple(outflow),
        trade_date=trade_date,
        sector_kind="industry",
        data_mode=data_mode,
        top_inflow_name=top_inflow.name if top_inflow else "",
        top_inflow_yi=top_inflow.net_flow_yi if top_inflow else 0.0,
        top_outflow_name=top_outflow.name if top_outflow else "",
        top_outflow_yi=top_outflow.net_flow_yi if top_outflow else 0.0,
    )


class IntradayBucketTimeTests(unittest.TestCase):
    def _dt(self, hour: int, minute: int) -> datetime:
        return datetime(2024, 6, 20, hour, minute, tzinfo=CHINA_TZ)

    def test_aligns_to_five_minute_bucket(self) -> None:
        label, minutes = intraday_bucket_time(self._dt(9, 32))
        self.assertEqual(label, "09:30")
        self.assertEqual(minutes, MORNING_OPEN_MIN)

    def test_clamps_lunch_break_to_morning_close(self) -> None:
        label, minutes = intraday_bucket_time(self._dt(12, 15))
        self.assertEqual(label, "11:30")
        self.assertEqual(minutes, MORNING_CLOSE_MIN)

    def test_clamps_after_close(self) -> None:
        _, minutes = intraday_bucket_time(self._dt(15, 20))
        self.assertEqual(minutes, AFTERNOON_CLOSE_MIN)


class BuildOverviewSnapshotTests(PgAppStorageTestCase):

    def test_empty_snapshot_returns_hint(self) -> None:
        snapshot = _snapshot([])
        overview = build_overview_snapshot(snapshot)
        self.assertEqual(overview.net_inflow_count, 0)
        self.assertIn("暂无", overview.empty_hint)

    def test_official_mode_uses_bar_series(self) -> None:
        rows = [
            _row("BK001", "互联网", 10.0),
            _row("BK002", "银行", -5.0),
        ]
        overview = build_overview_snapshot(_snapshot(rows, data_mode="official_dc"))
        self.assertFalse(overview.has_intraday_curve)
        self.assertEqual(overview.time_axis, ("收盘",))
        self.assertEqual(len(overview.inflow_series), 1)
        self.assertEqual(overview.inflow_series[0].points[0].bucket_time, "收盘")
        self.assertIn("日终", overview.empty_hint)

    def test_intraday_mode_builds_curve_from_samples(self) -> None:
        rows = [
            _row("BK001", "互联网", 10.0),
            _row("BK002", "银行", -5.0),
        ]
        upsert_intraday_samples(
            "2024-06-20",
            "industry",
            rows,
            bucket_time="09:30",
            clock_minutes=MORNING_OPEN_MIN,
        )
        upsert_intraday_samples(
            "2024-06-20",
            "industry",
            [_row("BK001", "互联网", 12.0), _row("BK002", "银行", -6.0)],
            bucket_time="09:35",
            clock_minutes=MORNING_OPEN_MIN + 5,
        )
        overview = build_overview_snapshot(_snapshot(rows, data_mode="intraday"))
        self.assertTrue(overview.has_intraday_curve)
        self.assertEqual(overview.time_axis, ("09:30", "09:35"))
        self.assertEqual(len(overview.inflow_series), 1)
        self.assertEqual(len(overview.inflow_series[0].points), 2)
        self.assertAlmostEqual(overview.inflow_series[0].latest_yi, 12.0)


class RecordIntradayOverviewSampleTests(PgAppStorageTestCase):

    @mock.patch("vnpy_ashare.services.sector_flow_overview.is_ashare_trading_session", return_value=True)
    def test_records_top_rows_during_intraday(self, _session: mock.Mock) -> None:
        rows = [_row(f"BK{i:03d}", f"板块{i}", float(i)) for i in range(1, 12)]
        rows.extend([_row(f"OUT{i:03d}", f"流出{i}", -float(i)) for i in range(1, 12)])
        snapshot = _snapshot(rows, data_mode="intraday")
        record_intraday_overview_sample(snapshot, dt=datetime(2024, 6, 20, 10, 3, tzinfo=CHINA_TZ))
        records = load_intraday_records(trade_date="2024-06-20", sector_kind="industry")
        sector_ids = {item.sector_id for item in records}
        self.assertLessEqual(len(sector_ids), 16)
        self.assertIn("BK011", sector_ids)
        self.assertIn("OUT011", sector_ids)

    @mock.patch("vnpy_ashare.services.sector_flow_overview.is_ashare_trading_session", return_value=False)
    def test_skips_when_not_trading_session(self, _session: mock.Mock) -> None:
        snapshot = _snapshot([_row("BK001", "互联网", 1.0)], data_mode="intraday")
        record_intraday_overview_sample(snapshot)
        records = load_intraday_records(trade_date="2024-06-20", sector_kind="industry")
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
