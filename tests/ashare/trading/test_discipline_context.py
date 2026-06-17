"""交易纪律上下文与 CSV 导出测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.position_snapshot import PositionSnapshot
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories import trade_journal as journal_repo
from vnpy_ashare.storage.repositories import trading_plans as plans_repo
from vnpy_ashare.trading.journal.discipline_context import (
    build_trading_discipline_snapshot,
    format_trading_discipline_extra,
)
from vnpy_ashare.trading.journal.report import format_journal_entries_csv


def _snap(**kwargs) -> PositionSnapshot:
    defaults = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-17",
        source="manual",
        last_price=9.0,
        market_value=900.0,
        unrealized_pnl=-100.0,
        unrealized_pnl_pct=-10.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )
    defaults.update(kwargs)
    return PositionSnapshot(**defaults)  # type: ignore[arg-type]


class DisciplineContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self._tmp.name)
        self._patcher = patch("vnpy_ashare.storage.connection._db_path", return_value=self.db_path)
        self._patcher.start()
        self._emotion_patcher = patch(
            "vnpy_ashare.trading.journal.plan_check.load_emotion_cycle_snapshot",
            return_value=None,
        )
        self._emotion_patcher.start()
        init_app_db()

    def tearDown(self) -> None:
        self._emotion_patcher.stop()
        self._patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_snapshot_includes_plan_and_journal(self) -> None:
        plan_id = plans_repo.create_trading_plan(
            trade_date="2026-06-17",
            max_position_pct=0.4,
            status="draft",
        )
        assert plan_id
        plans_repo.replace_trading_plan_symbols(plan_id, [("600519", Exchange.SSE)])
        plans_repo.activate_trading_plan(plan_id)
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="buy",
            trade_date="2026-06-17",
            price=100.0,
            volume=100,
            on_plan=True,
        )

        with (
            patch(
                "vnpy_ashare.trading.journal.discipline_context.today_trade_date",
                return_value="2026-06-17",
            ),
            patch(
                "vnpy_ashare.trading.risk.realized_pnl.today_trade_date",
                return_value="2026-06-17",
            ),
        ):
            snap = build_trading_discipline_snapshot()

        self.assertEqual(snap["trade_date"], "2026-06-17")
        self.assertEqual(snap["journal_today_count"], 1)
        plan = snap["trading_plan_summary"]
        assert isinstance(plan, dict)
        self.assertEqual(plan["watchlist"], ["600519.SSE"])

    def test_format_extra_off_plan_hint(self) -> None:
        plan_id = plans_repo.create_trading_plan(trade_date="2026-06-17", status="draft")
        assert plan_id
        plans_repo.replace_trading_plan_symbols(plan_id, [("600519", Exchange.SSE)])
        plans_repo.activate_trading_plan(plan_id)
        cache = {"600000.SSE": _snap()}

        with (
            patch(
                "vnpy_ashare.trading.journal.discipline_context.today_trade_date",
                return_value="2026-06-17",
            ),
            patch(
                "vnpy_ashare.trading.risk.realized_pnl.today_trade_date",
                return_value="2026-06-17",
            ),
        ):
            text = format_trading_discipline_extra(
                position_cache=cache,
                vt_symbol="600000.SSE",
                trade_date="2026-06-17",
            )

        self.assertIn("【交易纪律上下文】", text)
        self.assertIn("off_plan", text)

    def test_csv_export_header_and_row(self) -> None:
        journal_repo.insert_trade_journal_entry(
            symbol="600519",
            exchange="SSE",
            side="sell",
            trade_date="2026-06-17",
            price=110.0,
            volume=100,
            pnl=1000.0,
            on_plan=True,
        )
        csv_text = format_journal_entries_csv(
            start_date="2026-06-17",
            end_date="2026-06-17",
        )
        lines = csv_text.strip().splitlines()
        self.assertTrue(lines[0].startswith("trade_date,symbol"))
        self.assertIn("600519", lines[1])
        self.assertIn("sell", lines[1])


if __name__ == "__main__":
    unittest.main()
