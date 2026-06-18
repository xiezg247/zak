"""AI prompt 模板纯函数测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.ai.context.quote.prompts import (
    build_positions_ai_prompt,
    build_signal_panel_ai_prompt,
    build_signals_ai_prompt,
    build_trend_scenario_ai_prompt,
)


class TestPrompts(unittest.TestCase):
    def test_build_signals_ai_prompt_uses_custom_windows(self) -> None:
        prompt = build_signals_ai_prompt(
            "600000.SSE",
            "浦发银行",
            fast_window=8,
            slow_window=21,
        )
        self.assertIn("MA8/MA21", prompt)
        self.assertNotIn("list_strategy_signals", prompt)

    def test_build_signal_panel_ai_prompt_includes_snapshot(self) -> None:
        prompt = build_signal_panel_ai_prompt(
            "600000.SSE",
            "浦发银行",
            fast_window=8,
            slow_window=21,
            context_extra="策略信号：买入\n参考买价：10.00",
        )
        self.assertIn("已知信号区快照", prompt)
        self.assertIn("策略信号：买入", prompt)
        self.assertIn("MA8/MA21", prompt)
        self.assertNotIn("list_strategy_signals", prompt)

    def test_build_positions_ai_prompt_includes_context(self) -> None:
        prompt = build_positions_ai_prompt(
            "600000.SSE",
            "浦发银行",
            fast_window=10,
            slow_window=20,
            cost_price=10.5,
            volume=100,
            unrealized_pnl_pct=3.2,
            t1_locked=False,
        )
        self.assertNotIn("list_watchlist_positions", prompt)
        self.assertNotIn("list_strategy_signals", prompt)
        self.assertIn("10.50", prompt)
        self.assertIn("浮盈 +3.20%", prompt)
        self.assertIn("可卖", prompt)

    def test_build_trend_scenario_ai_prompt(self) -> None:
        prompt = build_trend_scenario_ai_prompt(
            "600000.SSE",
            "浦发银行",
            focus="5d",
            horizon_days=5,
            class_name="AshareDoubleMaStrategy",
            fast_window=8,
            slow_window=21,
        )
        self.assertIn("600000.SSE", prompt)
        self.assertIn("5 日", prompt)
        self.assertIn("MA8/MA21", prompt)
        self.assertIn("乐观/基准/悲观", prompt)
        self.assertIn("勿重复拉取", prompt)
        self.assertNotIn("trend_scenario_summary", prompt)
        self.assertNotIn("mcp_tdx_tdx_wenda_quotes", prompt)


if __name__ == "__main__":
    unittest.main()
