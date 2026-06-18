"""隔日退出 AI 工具测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from vnpy_ashare.trading.exit.for_symbol import (
    evaluate_all_overnight_exits,
    evaluate_overnight_exit_for_symbol,
)


class OvernightExitSkillTest(unittest.TestCase):
    def test_evaluate_for_symbol_without_position(self) -> None:
        with patch(
            "vnpy_ashare.trading.exit.for_symbol.load_position_row",
            return_value=None,
        ):
            payload = evaluate_overnight_exit_for_symbol("600519.SSE")
        self.assertIn("error", payload)

    def test_evaluate_for_symbol_stop_loss(self) -> None:
        row = {
            "symbol": "600519",
            "exchange": "SSE",
            "cost_price": 10.0,
            "volume": 100,
            "buy_date": "2026-06-15",
            "notes": "",
            "source": "manual",
        }
        quote_row = {
            "vt_symbol": "600519.SSE",
            "symbol": "600519",
            "last_price": 9.4,
            "prev_close": 9.5,
            "open_price": 9.5,
            "high_price": 9.6,
            "low_price": 9.3,
            "change_pct": -1.05,
            "volume_ratio": 0.8,
        }
        with (
            patch("vnpy_ashare.trading.exit.for_symbol.load_position_row", return_value=row),
            patch("vnpy_ashare.trading.exit.for_symbol.build_symbol_name_map", return_value={("600519", object()): "茅台"}),
            patch("vnpy_ashare.trading.exit.for_symbol.quotes_for_vt_symbols", return_value={"600519.SSE": quote_row}),
        ):
            payload = evaluate_overnight_exit_for_symbol("600519")

        self.assertEqual(payload["signal"], "sell")
        self.assertFalse(payload["t1_locked"])
        self.assertTrue(any(rule["rule_id"] == "stop_loss_pct" for rule in payload["rules"]))

    def test_trading_skill_evaluate_overnight_exit(self) -> None:
        from skills.vnpy_trading_skill import VnpyTradingSkill

        row = {
            "symbol": "600519",
            "exchange": "SSE",
            "cost_price": 10.0,
            "volume": 100,
            "buy_date": "2026-06-15",
            "notes": "",
            "source": "manual",
        }
        with (
            patch("vnpy_ashare.trading.exit.for_symbol.load_position_rows", return_value=[row]),
            patch("vnpy_ashare.trading.exit.for_symbol.build_symbol_name_map", return_value={}),
            patch(
                "vnpy_ashare.trading.exit.for_symbol.quotes_for_vt_symbols",
                return_value={"600519.SSE": {"vt_symbol": "600519.SSE", "last_price": 10.2, "prev_close": 10.0, "open_price": 10.1}},
            ),
        ):
            skill = VnpyTradingSkill()
            skill.setup()
            payload = json.loads(skill.evaluate_overnight_exit())

        self.assertIn("items", payload)
        self.assertEqual(payload["hold_count"], 1)

    def test_evaluate_all_empty(self) -> None:
        with patch("vnpy_ashare.trading.exit.for_symbol.load_position_rows", return_value=[]):
            payload = evaluate_all_overnight_exits()
        self.assertEqual(payload["items"], [])


if __name__ == "__main__":
    unittest.main()
