"""账户风控闸 + 情绪周期合并快照。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot, load_emotion_cycle_snapshot
from vnpy_ashare.trading.risk.gate import RiskGateSnapshot, build_risk_gate_snapshot, read_total_capital

if TYPE_CHECKING:
    from vnpy_ashare.domain.trading.position import PositionSnapshot


class CombinedRiskGateSnapshot(FrozenModel):
    account: RiskGateSnapshot = Field(description="账户风控闸快照")
    emotion: EmotionCycleSnapshot | None = Field(description="情绪周期快照")
    allow_new_positions: bool = Field(description="是否允许新开仓")
    emotion_position_pct_min: float | None = Field(description="情绪建议仓位下限（0–1）")
    emotion_position_pct_max: float | None = Field(description="情绪建议仓位上限（0–1）")
    actual_position_pct: float | None = Field(description="实际仓位占比（0–1）")
    total_capital: float | None = Field(description="总资金")
    warnings: tuple[str, ...] = Field(description="风险提示列表")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allow_new_positions": self.allow_new_positions,
            "account": {
                "state": self.account.state,
                "state_label": self.account.state_label,
                "allow_new_positions": self.account.allow_new_positions,
                "daily_pnl_pct": self.account.daily_pnl_pct,
                "avg_float_pnl_pct": self.account.avg_float_pnl_pct,
                "warnings": list(self.account.warnings),
            },
            "warnings": list(self.warnings),
        }
        if self.emotion is not None:
            payload["emotion"] = {
                "stage": self.emotion.stage,
                "stage_label": self.emotion.stage_label,
                "position_pct_min": self.emotion.position_pct_min,
                "position_pct_max": self.emotion.position_pct_max,
                "allow_new_positions": self.emotion.allow_new_positions,
            }
        if self.emotion_position_pct_min is not None:
            payload["emotion_position_pct_min"] = self.emotion_position_pct_min
        if self.emotion_position_pct_max is not None:
            payload["emotion_position_pct_max"] = self.emotion_position_pct_max
        if self.actual_position_pct is not None:
            payload["actual_position_pct"] = self.actual_position_pct
        if self.total_capital is not None:
            payload["total_capital"] = self.total_capital
        return payload


def compute_avg_float_pnl_pct(
    position_cache: Mapping[str, PositionSnapshot] | None,
) -> float | None:
    if not position_cache:
        return None
    pnls = [snap.unrealized_pnl_pct for snap in position_cache.values() if snap.unrealized_pnl_pct is not None]
    if not pnls:
        return None
    return sum(pnls) / len(pnls)


def compute_actual_position_pct(
    *,
    total_capital: float | None,
    position_cache: Mapping[str, PositionSnapshot] | None,
) -> float | None:
    if total_capital is None or total_capital <= 0 or not position_cache:
        return None
    total_mv = sum(snap.market_value for snap in position_cache.values() if snap.market_value is not None and snap.market_value > 0)
    if total_mv <= 0:
        return 0.0
    return round(total_mv / total_capital, 4)


def _merge_warnings(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for warning in group:
            if warning in seen:
                continue
            seen.add(warning)
            merged.append(warning)
    return tuple(merged)


def load_combined_risk_gate_snapshot(
    *,
    avg_float_pnl_pct: float | None = None,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
) -> CombinedRiskGateSnapshot:
    account = build_risk_gate_snapshot(avg_float_pnl_pct=avg_float_pnl_pct)
    emotion = load_emotion_cycle_snapshot()  # 默认不拉全市场，仅缓存
    total_capital = read_total_capital()
    actual = compute_actual_position_pct(
        total_capital=total_capital,
        position_cache=position_cache,
    )
    allow_emotion = emotion.allow_new_positions if emotion is not None else True
    return CombinedRiskGateSnapshot(
        account=account,
        emotion=emotion,
        allow_new_positions=account.allow_new_positions and allow_emotion,
        emotion_position_pct_min=emotion.position_pct_min if emotion is not None else None,
        emotion_position_pct_max=emotion.position_pct_max if emotion is not None else None,
        actual_position_pct=actual,
        total_capital=total_capital,
        warnings=_merge_warnings(account.warnings, emotion.warnings if emotion is not None else ()),
    )


def format_emotion_position_hint(
    *,
    position_pct_min: float | None,
    position_pct_max: float | None,
) -> str | None:
    if position_pct_max is None:
        return None
    pos_max = int(position_pct_max * 100)
    if position_pct_min is not None and position_pct_min > 0:
        pos_min = int(position_pct_min * 100)
        return f"情绪建议 {pos_min}–{pos_max}%"
    return f"情绪建议 ≤{pos_max}%"
