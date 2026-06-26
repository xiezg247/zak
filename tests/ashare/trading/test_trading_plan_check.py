"""交易计划校验测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from tests.ashare.pg_unittest import PgStorageTestCase
from vnpy_ashare.storage.repositories import trading_plans as plans_repo
from vnpy_ashare.trading.plan.plan_check import check_buy_against_plan


class TradingPlanCheckTests(PgStorageTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._emotion_patcher = patch(
            "vnpy_ashare.trading.plan.plan_check.load_emotion_cycle_snapshot",
            return_value=None,
        )
        self._emotion_patcher.start()

    def tearDown(self) -> None:
        self._emotion_patcher.stop()
        super().tearDown()

    def test_off_plan_when_not_in_active_plan(self) -> None:
        plan_id = plans_repo.create_trading_plan(
            trade_date="2026-06-17",
            max_position_pct=0.5,
            status="draft",
        )
        assert plan_id
        plans_repo.replace_trading_plan_symbols(plan_id, [("600519", Exchange.SSE)])
        plans_repo.activate_trading_plan(plan_id)

        check = check_buy_against_plan("600000", Exchange.SSE, trade_date="2026-06-17")
        self.assertFalse(check.on_plan)
        self.assertIn("off_plan", check.violation_tags)

        check_ok = check_buy_against_plan("600519", Exchange.SSE, trade_date="2026-06-17")
        self.assertTrue(check_ok.on_plan)
        self.assertNotIn("off_plan", check_ok.violation_tags)


if __name__ == "__main__":
    unittest.main()
