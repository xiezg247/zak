"""市场 AI prompt 与笔记中心计划 Tab 测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.ai.context.market_overview import (
    build_market_ai_prompt,
    format_limit_ladder_line,
)
from vnpy_ashare.domain.trading.plan import TradingPlanRecord, TradingPlanSymbolRecord
from vnpy_ashare.ui.features.notes_center.plans_view import _format_plan_detail, _format_plan_item


class MarketAiPromptTest(unittest.TestCase):
    def test_format_limit_ladder_line(self) -> None:
        line = format_limit_ladder_line({"首板": 12, "2板": 3, "3板": 1})
        self.assertIn("连板梯队", line)
        self.assertIn("首板×12", line)
        self.assertIn("最高 3 板", line)

    def test_build_market_ai_prompt_contains_sections(self) -> None:
        prompt = build_market_ai_prompt(focus="intraday")
        self.assertIn("极致短线", prompt)
        self.assertIn("get_emotion_cycle", prompt)


class NotesCenterPlansFormatTest(unittest.TestCase):
    def test_format_plan_item_and_detail(self) -> None:
        plan = TradingPlanRecord(
            id="p1",
            trade_date="2026-06-19",
            emotion_expected="startup",
            max_position_pct=0.5,
            notes="观察龙头",
            status="active",
            created_at="2026-06-18T20:00:00",
            updated_at="2026-06-18T20:00:00",
            symbols=(
                TradingPlanSymbolRecord(
                    symbol="600519",
                    exchange="SSE",
                    allowed_modes=("limit_board",),
                    entry_conditions="",
                    exit_conditions="",
                    sort_order=0,
                ),
            ),
        )
        self.assertIn("已激活", _format_plan_item(plan))
        detail = _format_plan_detail(plan)
        self.assertIn("600519.SSE", detail)
        self.assertIn("启动", detail)


if __name__ == "__main__":
    unittest.main()
