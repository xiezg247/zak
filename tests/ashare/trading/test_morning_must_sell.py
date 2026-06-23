"""上午必卖异动标签测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.trading.exit import ExitRuleHit
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.exit.morning_must_sell import (
    is_morning_sell_reminder_window,
    should_tag_morning_must_sell,
)


def _snap(**kwargs) -> PositionSnapshot:
    base = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
        source="manual",
        last_price=9.8,
        market_value=980.0,
        unrealized_pnl=-20.0,
        unrealized_pnl_pct=-2.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
        exit_rules=(),
    )
    base.update(kwargs)
    return PositionSnapshot(**base)  # type: ignore[arg-type]


def _quote(**kwargs) -> QuoteSnapshot:
    base = dict(
        symbol="600000.SH",
        name="测试",
        last_price=9.8,
        prev_close=10.0,
        open_price=9.9,
        high_price=10.0,
        low_price=9.7,
        change_amount=-0.2,
        change_pct=-2.0,
        turnover_rate=1.0,
        volume=1000.0,
        volume_ratio=0.8,
    )
    base.update(kwargs)
    return QuoteSnapshot(**base)


class MorningMustSellTests(unittest.TestCase):
    def test_reminder_window_afternoon(self) -> None:
        dt = datetime(2026, 6, 23, 14, 0, tzinfo=CHINA_TZ)
        with patch("vnpy_ashare.trading.exit.morning_must_sell.is_trading_day", return_value=True):
            with patch(
                "vnpy_ashare.trading.exit.morning_must_sell.is_ashare_trading_session",
                return_value=True,
            ):
                self.assertTrue(is_morning_sell_reminder_window(dt))

    def test_no_tag_when_t1_locked(self) -> None:
        dt = datetime(2026, 6, 23, 14, 0, tzinfo=CHINA_TZ)
        self.assertFalse(
            should_tag_morning_must_sell(
                snap=_snap(t1_locked=True),
                quote=_quote(),
                now=dt,
            )
        )

    def test_no_tag_when_exit_signal_sell(self) -> None:
        dt = datetime(2026, 6, 23, 14, 0, tzinfo=CHINA_TZ)
        self.assertFalse(
            should_tag_morning_must_sell(
                snap=_snap(exit_signal="sell"),
                quote=_quote(),
                now=dt,
            )
        )

    def test_afternoon_weakness(self) -> None:
        dt = datetime(2026, 6, 23, 14, 0, tzinfo=CHINA_TZ)
        self.assertTrue(
            should_tag_morning_must_sell(
                snap=_snap(),
                quote=_quote(change_pct=-1.5),
                now=dt,
            )
        )

    def test_late_morning_near_rule(self) -> None:
        dt = datetime(2026, 6, 23, 11, 15, tzinfo=CHINA_TZ)
        rules = (
            ExitRuleHit(
                rule_id="take_profit_weak_volume",
                label="冲高量能不足",
                status="near",
                detail="test",
            ),
        )
        self.assertTrue(
            should_tag_morning_must_sell(
                snap=_snap(exit_rules=rules),
                quote=_quote(change_pct=1.0),
                now=dt,
            )
        )


if __name__ == "__main__":
    unittest.main()
