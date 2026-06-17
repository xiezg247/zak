"""风控闸状态机（MVP）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnpy_ashare.config.preferences._settings import coerce_settings_int, get_settings

RiskGateState = Literal["normal", "caution", "halt"]

_STATE_LABELS: dict[RiskGateState, str] = {
    "normal": "正常",
    "caution": "警戒",
    "halt": "熔断",
}


@dataclass(frozen=True)
class RiskGateSnapshot:
    state: RiskGateState
    state_label: str
    allow_new_positions: bool
    daily_pnl_pct: float | None
    avg_float_pnl_pct: float | None
    warnings: tuple[str, ...]


def _read_float(key: str) -> float | None:
    raw = get_settings().value(key)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object, *, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class RiskGateEngine:
    """依据 QSettings 阈值与持仓浮盈均值评估风控状态。"""

    def __init__(self) -> None:
        self._last_state: RiskGateState | None = None
        self._last_snapshot: RiskGateSnapshot | None = None

    @property
    def last_snapshot(self) -> RiskGateSnapshot | None:
        return self._last_snapshot

    def evaluate(self, *, avg_float_pnl_pct: float | None = None) -> RiskGateSnapshot | None:
        settings = get_settings()
        daily_pnl = _read_float("trading/risk/daily_pnl_pct")
        caution_daily = _coerce_float(settings.value("trading/risk/caution_daily_pct"), default=-3.0)
        halt_daily = _coerce_float(settings.value("trading/risk/halt_daily_pct"), default=-5.0)
        caution_float = _coerce_float(settings.value("trading/risk/caution_float_pct"), default=-5.0)

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

        if coerce_settings_int(settings.value("trading/risk/manual_halt"), default=0):
            state = "halt"
            warnings.append("手动熔断已开启")

        snapshot = RiskGateSnapshot(
            state=state,
            state_label=_STATE_LABELS[state],
            allow_new_positions=state == "normal",
            daily_pnl_pct=daily_pnl,
            avg_float_pnl_pct=avg_float_pnl_pct,
            warnings=tuple(warnings),
        )
        self._last_snapshot = snapshot
        if snapshot.state == self._last_state:
            return None
        self._last_state = snapshot.state
        return snapshot
