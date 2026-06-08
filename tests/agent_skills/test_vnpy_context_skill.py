"""vnpy_context_skill 测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401

from vnpy.trader.constant import Exchange

from skills.vnpy_context_skill import VnpyContextSkill
from vnpy_ashare.ai.session_context import (
    BacktestSummary,
    clear_session_context,
    set_ai_context,
    set_backtest_summary,
)
from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.models import StockItem
from vnpy_ashare.ai.context import AiContextData
from vnpy_skills.engine import SkillEngine


class SymbolTests(unittest.TestCase):
    def test_vt_symbol(self) -> None:
        item = parse_stock_symbol("600519.SSE")
        assert item is not None
        self.assertEqual(item.vt_symbol, "600519.SSE")


class VnpyContextSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_session_context()
        self.skill = VnpyContextSkill()
        self.skill.setup()

    def tearDown(self) -> None:
        clear_session_context()

    def test_get_quote_context_empty(self) -> None:
        payload = json.loads(self.skill.get_quote_context())
        self.assertIn("message", payload)

    def test_get_quote_context_with_data(self) -> None:
        set_ai_context(
            AiContextData(
                page="自选",
                symbol="600519",
                exchange="SSE",
                name="贵州茅台",
                quote_summary="最新价 1500.00",
                extra="本地日 K 条数：120",
            )
        )
        payload = json.loads(self.skill.get_quote_context())
        self.assertEqual(payload["name"], "贵州茅台")
        self.assertIn("1500", payload["quote_summary"])

    @patch("skills.vnpy_context_skill.load_watchlist")
    def test_get_watchlist(self, mock_load) -> None:
        mock_load.return_value = [
            StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台"),
        ]
        payload = json.loads(self.skill.get_watchlist())
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["name"], "贵州茅台")

    @patch("skills.vnpy_context_skill.get_period_overview")
    @patch("skills.vnpy_context_skill.load_scope_bars")
    def test_get_bars_summary(self, mock_load_bars, mock_overview) -> None:
        from datetime import datetime

        from vnpy.trader.object import BarData

        mock_overview.return_value = type(
            "O",
            (),
            {
                "count": 100,
                "start": datetime(2024, 1, 1),
                "end": datetime(2025, 1, 1),
            },
        )()
        mock_load_bars.return_value = [
            BarData(
                gateway_name="TEST",
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=datetime(2024, 12, 1),
                interval=None,
                volume=1,
                open_price=100,
                high_price=101,
                low_price=99,
                close_price=100,
            ),
            BarData(
                gateway_name="TEST",
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=datetime(2024, 12, 31),
                interval=None,
                volume=1,
                open_price=110,
                high_price=111,
                low_price=109,
                close_price=110,
            ),
        ]
        payload = json.loads(self.skill.get_bars_summary("600519.SSE"))
        self.assertEqual(payload["count"], 100)
        self.assertEqual(payload["lookback_return_pct"], 10.0)

    def test_get_backtest_summary_empty(self) -> None:
        payload = json.loads(self.skill.get_backtest_summary())
        self.assertIn("暂无回测摘要", payload["message"])

    def test_get_backtest_summary_with_data(self) -> None:
        set_backtest_summary(
            BacktestSummary(
                strategy="AshareDoubleMaStrategy",
                vt_symbol="600519.SSE",
                interval="d",
                start="2024-01-01",
                end="2024-12-31",
                statistics={"total_return": 12.5, "max_drawdown": -8.2},
            )
        )
        payload = json.loads(self.skill.get_backtest_summary())
        self.assertEqual(payload["strategy"], "AshareDoubleMaStrategy")
        self.assertEqual(payload["statistics"]["total_return"], 12.5)


class SkillEngineIntegrationTests(unittest.TestCase):
    def test_load_vnpy_context_skill(self) -> None:
        engine = SkillEngine()
        engine.load_all()
        enabled = engine.init_skills()
        self.assertIn("vnpy-context", enabled)
        tool_names = {spec.name for spec in engine.get_tool_specs()}
        self.assertIn("get_watchlist", tool_names)
        self.assertIn("get_bars_summary", tool_names)


if __name__ == "__main__":
    unittest.main()
