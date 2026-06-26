"""板块资金盘中采样仓储测试。"""

from __future__ import annotations

import unittest

from tests.ashare.pg_unittest import PgAppStorageTestCase
from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.storage.repositories.sector_flow_intraday import (
    load_intraday_records,
    purge_intraday_before,
    upsert_intraday_samples,
)


def _row(sector_id: str, name: str, net_flow_yi: float) -> SectorFlowRow:
    return SectorFlowRow(
        sector_id=sector_id,
        name=name,
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=net_flow_yi,
        stock_count=5,
        up_ratio=0.4,
        flow_source="dc_industry",
        sector_kind="industry",
    )


class SectorFlowIntradayRepositoryTests(PgAppStorageTestCase):

    def test_upsert_and_load(self) -> None:
        upsert_intraday_samples(
            "2024-06-20",
            "industry",
            [_row("BK001", "互联网", 10.0)],
            bucket_time="09:30",
            clock_minutes=570,
        )
        records = load_intraday_records(trade_date="2024-06-20", sector_kind="industry")
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0].net_flow_yi, 10.0)

    def test_upsert_conflict_updates_values(self) -> None:
        upsert_intraday_samples(
            "2024-06-20",
            "industry",
            [_row("BK001", "互联网", 10.0)],
            bucket_time="09:30",
            clock_minutes=570,
        )
        upsert_intraday_samples(
            "2024-06-20",
            "industry",
            [_row("BK001", "互联网", 12.5)],
            bucket_time="09:30",
            clock_minutes=570,
        )
        records = load_intraday_records(trade_date="2024-06-20", sector_kind="industry")
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0].net_flow_yi, 12.5)

    def test_purge_intraday_before(self) -> None:
        upsert_intraday_samples(
            "2024-06-19",
            "industry",
            [_row("BK001", "互联网", 1.0)],
            bucket_time="09:30",
            clock_minutes=570,
        )
        upsert_intraday_samples(
            "2024-06-20",
            "industry",
            [_row("BK001", "互联网", 2.0)],
            bucket_time="09:30",
            clock_minutes=570,
        )
        purge_intraday_before("2024-06-20")
        old = load_intraday_records(trade_date="2024-06-19", sector_kind="industry")
        current = load_intraday_records(trade_date="2024-06-20", sector_kind="industry")
        self.assertEqual(old, [])
        self.assertEqual(len(current), 1)


if __name__ == "__main__":
    unittest.main()
