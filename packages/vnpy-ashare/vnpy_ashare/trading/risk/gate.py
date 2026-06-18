"""风控闸状态机（MVP + 周期回撤）。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.domain.trading.risk import RiskGateSnapshot, RiskGateState
from vnpy_ashare.trading.risk.drawdown import evaluate_drawdown, is_halt_active

if TYPE_CHECKING:
    from vnpy_ashare.domain.trading.position import PositionSnapshot

__all__ = ["RiskGateSnapshot", "RiskGateState", "build_risk_gate_snapshot", "read_total_capital"]

_STATE_LABELS: dict[RiskGateState, str] = {
    "normal": "正常",
    "caution": "警戒",
    "halt": "熔断",
}


def read_total_capital() -> float | None:
    return load_trading_risk_prefs().total_capital


def build_risk_gate_snapshot(
    *,
    avg_float_pnl_pct: float | None = None,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
) -> RiskGateSnapshot:
    """评估当前风控闸快照（无状态变更检测）。"""
    prefs = load_trading_risk_prefs()
    _, weekly_dd, total_dd, drawdown_warnings = evaluate_drawdown(
        prefs,
        position_cache=position_cache,
        persist=True,
    )
    prefs = load_trading_risk_prefs()

    caution_daily = prefs.caution_daily_pct
    halt_daily = prefs.halt_daily_pct
    caution_float = prefs.caution_float_pct

    warnings: list[str] = list(drawdown_warnings)
    state: RiskGateState = "normal"
    daily_pnl = prefs.daily_pnl_pct

    if daily_pnl is not None and daily_pnl <= halt_daily:
        state = "halt"
        warnings.append(f"当日盈亏 {daily_pnl:.1f}% 触发熔断阈值")
    elif daily_pnl is not None and daily_pnl <= caution_daily:
        state = "caution"
        warnings.append(f"当日盈亏 {daily_pnl:.1f}% 触发警戒阈值")
    elif avg_float_pnl_pct is not None and avg_float_pnl_pct <= caution_float:
        state = "caution"
        warnings.append(f"持仓平均浮盈 {avg_float_pnl_pct:.1f}% 触发警戒")

    if prefs.manual_halt:
        state = "halt"
        warnings.append("手动熔断已开启")

    halt_until = prefs.halt_until
    if is_halt_active(prefs):
        state = "halt"
        if prefs.halt_reason == "total_drawdown":
            if total_dd is not None:
                warnings.append(f"总回撤 {total_dd:.1f}% 触发停手 {halt_until or ''}")
        elif prefs.halt_reason == "weekly_drawdown":
            if weekly_dd is not None:
                warnings.append(f"单周回撤 {weekly_dd:.1f}% 触发停手 {halt_until or ''}")

    elif total_dd is not None and total_dd <= -5.0 and state == "normal":
        state = "caution"

    return RiskGateSnapshot(
        state=state,
        state_label=_STATE_LABELS[state],
        allow_new_positions=state == "normal",
        daily_pnl_pct=daily_pnl,
        avg_float_pnl_pct=avg_float_pnl_pct,
        weekly_drawdown_pct=weekly_dd,
        total_drawdown_pct=total_dd,
        halt_until=halt_until,
        warnings=tuple(_dedupe_warnings(warnings)),
    )


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        merged.append(warning)
    return merged


class RiskGateEngine:
    """依据 QSettings 阈值与持仓浮盈均值评估风控状态。"""

    def __init__(self) -> None:
        self._last_state: RiskGateState | None = None
        self._last_snapshot: RiskGateSnapshot | None = None

    @property
    def last_snapshot(self) -> RiskGateSnapshot | None:
        return self._last_snapshot

    def evaluate(
        self,
        *,
        avg_float_pnl_pct: float | None = None,
        position_cache: Mapping[str, PositionSnapshot] | None = None,
    ) -> RiskGateSnapshot | None:
        snapshot = build_risk_gate_snapshot(
            avg_float_pnl_pct=avg_float_pnl_pct,
            position_cache=position_cache,
        )
        self._last_snapshot = snapshot
        if snapshot.state == self._last_state:
            return None
        self._last_state = snapshot.state
        return snapshot
