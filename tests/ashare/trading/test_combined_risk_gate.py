"""合并风控闸测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from vnpy_ashare.domain.position_snapshot import PositionSnapshot
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot
from vnpy_ashare.trading.risk.combined import (
    compute_actual_position_pct,
    compute_avg_float_pnl_pct,
    format_emotion_position_hint,
    load_combined_risk_gate_snapshot,
)
from vnpy_ashare.trading.risk.gate import build_risk_gate_snapshot


def _snap(vt_symbol: str, *, pnl_pct: float | None = None, market_value: float | None = None) -> PositionSnapshot:
    return PositionSnapshot(
        vt_symbol=vt_symbol,
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-17",
        source="manual",
        last_price=10.0,
        market_value=market_value,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=pnl_pct,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )


def _emotion(*, stage: str = "startup", allow: bool = True) -> EmotionCycleSnapshot:
    return EmotionCycleSnapshot(
        stage=stage,  # type: ignore[arg-type]
        stage_label="启动",
        position_pct_min=0.30,
        position_pct_max=0.50,
        position_factor=0.4,
        allowed_modes=("limit_board",),
        allow_new_positions=allow,
        warnings=() if allow else ("退潮期不建议新开仓",),
        inputs={"limit_up_count": 50, "limit_down_count": 3},
        updated_at="2026-06-17 10:00",
    )


class CombinedRiskGateTest(unittest.TestCase):
    def test_build_halt_disallows_new_positions(self) -> None:
        from vnpy_ashare.config.preferences.trading_risk import TradingRiskPrefs

        prefs = TradingRiskPrefs(
            total_capital=100_000.0,
            per_trade_risk_pct=0.02,
            stop_loss_pct=0.05,
            daily_pnl_pct=-6.0,
            realized_pnl_today=None,
            caution_daily_pct=-3.0,
            halt_daily_pct=-5.0,
            caution_float_pct=-5.0,
            manual_halt=False,
        )
        with patch("vnpy_ashare.trading.risk.gate.load_trading_risk_prefs", return_value=prefs):
            snap = build_risk_gate_snapshot()
        self.assertEqual(snap.state, "halt")
        self.assertFalse(snap.allow_new_positions)

    def test_avg_float_pnl_and_actual_position_pct(self) -> None:
        cache = {
            "600519.SSE": _snap("600519.SSE", pnl_pct=-6.0, market_value=30000.0),
            "000001.SZSE": _snap("000001.SZSE", pnl_pct=-4.0, market_value=20000.0),
        }
        self.assertAlmostEqual(compute_avg_float_pnl_pct(cache), -5.0)
        self.assertAlmostEqual(
            compute_actual_position_pct(total_capital=100000.0, position_cache=cache),
            0.5,
        )

    def test_recession_plus_halt_merged(self) -> None:
        from vnpy_ashare.trading.risk.gate import RiskGateSnapshot

        recession = _emotion(stage="recession", allow=False)
        recession = EmotionCycleSnapshot(
            stage="recession",
            stage_label="退潮",
            position_pct_min=0.0,
            position_pct_max=0.0,
            position_factor=0.0,
            allowed_modes=(),
            allow_new_positions=False,
            warnings=("退潮期不建议新开仓",),
            inputs={"limit_up_count": 10, "limit_down_count": 20},
            updated_at="2026-06-17 10:00",
        )
        halt = RiskGateSnapshot(
            state="halt",
            state_label="熔断",
            allow_new_positions=False,
            daily_pnl_pct=-6.0,
            avg_float_pnl_pct=None,
            warnings=("当日盈亏 -6.0% 触发熔断阈值",),
        )
        with patch(
            "vnpy_ashare.trading.risk.combined.load_emotion_cycle_snapshot",
            return_value=recession,
        ), patch(
            "vnpy_ashare.trading.risk.combined.build_risk_gate_snapshot",
            return_value=halt,
        ):
            combined = load_combined_risk_gate_snapshot()
        self.assertFalse(combined.allow_new_positions)
        self.assertIn("当日盈亏", combined.warnings[0])
        self.assertIn("退潮", combined.warnings[-1])

    def test_format_emotion_position_hint(self) -> None:
        self.assertEqual(format_emotion_position_hint(position_pct_min=0.3, position_pct_max=0.5), "情绪建议 30–50%")
        self.assertEqual(format_emotion_position_hint(position_pct_min=0.0, position_pct_max=0.5), "情绪建议 ≤50%")

    def test_trading_skill_check_risk_gate(self) -> None:
        from skills.vnpy_trading_skill import VnpyTradingSkill

        skill = VnpyTradingSkill()
        skill.setup()
        payload = json.loads(skill.check_risk_gate())
        self.assertIn("allow_new_positions", payload)
        self.assertIn("account", payload)


if __name__ == "__main__":
    unittest.main()
