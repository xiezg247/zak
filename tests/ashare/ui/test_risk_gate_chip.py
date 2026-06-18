"""风控闸芯片文案测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.emotion import EmotionCycleSnapshot
from vnpy_ashare.domain.trading.risk import CombinedRiskGateSnapshot, RiskGateSnapshot
from vnpy_ashare.ui.quotes.market_overview.risk_gate_chip import (
    build_risk_gate_chip_tooltip,
    format_risk_gate_chip_value,
)


def _account(state: str, **kwargs) -> RiskGateSnapshot:
    labels = {"normal": "正常", "caution": "警戒", "halt": "熔断"}
    return RiskGateSnapshot(
        state=state,  # type: ignore[arg-type]
        state_label=labels[state],
        allow_new_positions=state != "halt",
        daily_pnl_pct=kwargs.get("daily_pnl_pct"),
        avg_float_pnl_pct=kwargs.get("avg_float_pnl_pct"),
        weekly_drawdown_pct=kwargs.get("weekly_drawdown_pct"),
        total_drawdown_pct=kwargs.get("total_drawdown_pct"),
        halt_until=kwargs.get("halt_until"),
        warnings=kwargs.get("warnings", ()),
    )


class RiskGateChipTextTest(unittest.TestCase):
    def test_halt_shows_stop_label(self) -> None:
        combined = CombinedRiskGateSnapshot(
            account=_account("halt", halt_until="2026-06-20"),
            emotion=None,
            allow_new_positions=False,
            emotion_position_pct_min=None,
            emotion_position_pct_max=None,
            actual_position_pct=None,
            total_capital=1_000_000,
            warnings=("总回撤熔断",),
        )
        self.assertIn("停手", format_risk_gate_chip_value(combined))
        self.assertIn("熔断至", build_risk_gate_chip_tooltip(combined))

    def test_caution_with_emotion_block(self) -> None:
        emotion = EmotionCycleSnapshot(
            stage="recession",
            stage_label="退潮",
            position_factor=0.3,
            position_pct_min=0.0,
            position_pct_max=0.2,
            allow_new_positions=False,
            allowed_modes=(),
            warnings=("退潮期",),
            inputs={},
            updated_at="2026-06-18T10:00:00",
        )
        combined = CombinedRiskGateSnapshot(
            account=_account("normal"),
            emotion=emotion,
            allow_new_positions=False,
            emotion_position_pct_min=0.0,
            emotion_position_pct_max=0.2,
            actual_position_pct=0.35,
            total_capital=None,
            warnings=("实际仓位偏高",),
        )
        self.assertIn("慎开", format_risk_gate_chip_value(combined))
        tooltip = build_risk_gate_chip_tooltip(combined)
        self.assertIn("退潮", tooltip)
        self.assertIn("35.0%", tooltip)


if __name__ == "__main__":
    unittest.main()
