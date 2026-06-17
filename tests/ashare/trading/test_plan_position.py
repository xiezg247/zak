"""计划仓位与分组汇总测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.position_snapshot import PositionRecord, PositionSnapshot
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import positions as positions_repo
from vnpy_ashare.storage.repositories import watchlist as watchlist_repo
from vnpy_ashare.storage.repositories import watchlist_groups as groups_repo
from vnpy_ashare.trading.risk.plan_position import (
    format_group_position_tab_label,
    format_plan_vs_actual_cell,
    summarize_group_position,
    sum_plan_pct,
)


class PlanPositionTests(unittest.TestCase):
    def test_sum_plan_pct(self) -> None:
        records = [
            PositionRecord("600000", "SSE", "", 10.0, 100, "2026-06-01", plan_pct=0.2),
            PositionRecord("600519", "SSE", "", 10.0, 100, "2026-06-01", plan_pct=0.1),
            PositionRecord("000001", "SZSE", "", 10.0, 100, "2026-06-01"),
        ]
        self.assertAlmostEqual(sum_plan_pct(records), 0.3)

    def test_format_plan_vs_actual_cell(self) -> None:
        text, tip = format_plan_vs_actual_cell(plan_pct=0.2, actual_pct=0.25)
        self.assertEqual(text, "20/25%")
        self.assertIn("超计划", tip)

    def test_group_position_summary(self) -> None:
        records = [
            PositionRecord("600519", "SSE", "", 100.0, 100, "2026-06-01", plan_pct=0.15),
        ]
        cache = {
            "600519.SSE": PositionSnapshot(
                vt_symbol="600519.SSE",
                name="茅台",
                cost_price=100.0,
                volume=100,
                buy_date="2026-06-01",
                source="manual",
                last_price=110.0,
                market_value=11000.0,
                unrealized_pnl=1000.0,
                unrealized_pnl_pct=10.0,
                exit_signal="hold",
                signal_snapshot=None,
                t1_locked=False,
                exit_ref_price=None,
                dist_exit_pct=None,
                warnings=(),
            )
        }
        summary = summarize_group_position(
            group_id="g1",
            member_keys={("600519", "SSE")},
            records=records,
            position_cache=cache,
            total_capital=100_000.0,
            position_cap_pct=0.2,
        )
        self.assertAlmostEqual(summary.actual_pct or 0, 0.11, places=2)
        self.assertFalse(summary.over_cap)
        label = format_group_position_tab_label("短线观察", summary)
        self.assertIn("11/20%", label)


class PlanPositionDbTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_position_plan_pct_roundtrip(self) -> None:
        watchlist_repo.add_watchlist_item("600000", Exchange.SSE, "浦发银行")
        self.assertTrue(
            positions_repo.add_position_item(
                "600000",
                Exchange.SSE,
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
                plan_pct=0.2,
            )
        )
        rows = positions_repo.load_position_rows()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(float(rows[0]["plan_pct"]), 0.2)

    def test_group_position_cap_roundtrip(self) -> None:
        group_id = groups_repo.create_watchlist_group("核心")
        assert group_id
        self.assertTrue(groups_repo.update_watchlist_group_position_cap(group_id, 0.25))
        groups = groups_repo.load_watchlist_groups()
        self.assertAlmostEqual(groups[0].position_cap_pct or 0, 0.25)


if __name__ == "__main__":
    unittest.main()
