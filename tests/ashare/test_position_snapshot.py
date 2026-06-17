"""持仓快照域模型测试。"""

from __future__ import annotations

import unittest
from datetime import date

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.trading.position import (
    PositionRecord,
    build_position_snapshot,
    compute_unrealized_pnl,
    position_row_sort_key,
    position_t1_locked,
)
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot


def _signal(signal: str = "hold") -> SignalSnapshot:
    return SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2026-06-10",
        signal=signal,  # type: ignore[arg-type]
        signal_label=signal,
        signal_date="2026-06-10",
        ref_buy_price=10.0,
        ref_sell_price=11.0,
        strength=50.0,
        reason_summary="test",
        reasons=("test",),
        warnings=(),
        last_close=10.5,
    )


class PositionSnapshotTests(unittest.TestCase):
    def test_compute_unrealized_pnl(self) -> None:
        mv, pnl, pct = compute_unrealized_pnl(10.0, 100, 11.0)
        self.assertEqual(mv, 1100.0)
        self.assertEqual(pnl, 100.0)
        self.assertEqual(pct, 10.0)

    def test_position_t1_locked(self) -> None:
        self.assertTrue(position_t1_locked("2026-06-11", trading_day=date(2026, 6, 11)))
        self.assertFalse(position_t1_locked("2026-06-10", trading_day=date(2026, 6, 11)))

    def test_t1_and_exit_signal_shown_separately(self) -> None:
        record = PositionRecord(
            symbol="000063",
            exchange="SZSE",
            name="中兴通讯",
            cost_price=30.0,
            volume=100,
            buy_date="2026-06-11",
        )
        snap = build_position_snapshot(
            record,
            signal=_signal("buy"),
            last_price=31.0,
            trading_day=date(2026, 6, 11),
        )
        self.assertTrue(snap.t1_locked)
        self.assertEqual(snap.t1_status_label, "T+1 锁定")
        self.assertEqual(snap.exit_signal, "buy")
        self.assertEqual(snap.exit_signal_label, "买入")

    def test_build_position_snapshot(self) -> None:
        record = PositionRecord(
            symbol="600000",
            exchange="SSE",
            name="浦发银行",
            cost_price=10.0,
            volume=100,
            buy_date="2026-06-10",
        )
        snap = build_position_snapshot(record, signal=_signal("sell"), last_price=10.5)
        self.assertEqual(snap.exit_signal, "sell")
        self.assertEqual(snap.unrealized_pnl, 50.0)
        self.assertFalse(snap.t1_locked)

    def test_position_row_sort_key_prioritizes_sell(self) -> None:
        sell_snap = build_position_snapshot(
            PositionRecord(
                symbol="600000",
                exchange="SSE",
                name="",
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
            ),
            signal=_signal("sell"),
            last_price=9.0,
        )
        hold_snap = build_position_snapshot(
            PositionRecord(
                symbol="600519",
                exchange="SSE",
                name="",
                cost_price=10.0,
                volume=100,
                buy_date="2026-06-01",
            ),
            signal=_signal("hold"),
            last_price=12.0,
        )
        self.assertLess(position_row_sort_key(sell_snap), position_row_sort_key(hold_snap))


if __name__ == "__main__":
    unittest.main()
