"""风控闸状态机（MVP）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.domain.trading.risk import RiskGateSnapshot, RiskGateState

__all__ = ["RiskGateSnapshot", "RiskGateState", "build_risk_gate_snapshot", "read_total_capital"]

_STATE_LABELS: dict[RiskGateState, str] = {
    "normal": "正常",
    "caution": "警戒",
    "halt": "熔断",
}


def read_total_capital() -> float | None:
    return load_trading_risk_prefs().total_capital


def build_risk_gate_snapshot(*, avg_float_pnl_pct: float | None = None) -> RiskGateSnapshot:
    """评估当前风控闸快照（无状态变更检测）。"""
    prefs = load_trading_risk_prefs()
    daily_pnl = prefs.daily_pnl_pct
    caution_daily = prefs.caution_daily_pct
    halt_daily = prefs.halt_daily_pct
    caution_float = prefs.caution_float_pct

    warnings: list[str] = []
    state: RiskGateState = "normal"

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

    return RiskGateSnapshot(
        state=state,
        state_label=_STATE_LABELS[state],
        allow_new_positions=state == "normal",
        daily_pnl_pct=daily_pnl,
        avg_float_pnl_pct=avg_float_pnl_pct,
        warnings=tuple(warnings),
    )


class RiskGateEngine:
    """依据 QSettings 阈值与持仓浮盈均值评估风控状态。"""

    def __init__(self) -> None:
        self._last_state: RiskGateState | None = None
        self._last_snapshot: RiskGateSnapshot | None = None

    @property
    def last_snapshot(self) -> RiskGateSnapshot | None:
        return self._last_snapshot

    def evaluate(self, *, avg_float_pnl_pct: float | None = None) -> RiskGateSnapshot | None:
        snapshot = build_risk_gate_snapshot(avg_float_pnl_pct=avg_float_pnl_pct)
        self._last_snapshot = snapshot
        if snapshot.state == self._last_state:
            return None
        self._last_state = snapshot.state
        return snapshot
