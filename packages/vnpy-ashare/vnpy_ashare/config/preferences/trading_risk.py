"""交易参数 QSettings（总资金、止损、浮亏阈值等）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_common.domain.base import FrozenModel

PREFIX = "trading/risk"

DEFAULT_STOP_LOSS_PCT = 0.05
DEFAULT_CAUTION_FLOAT_PCT = -5.0


def _coerce_float(value: object, *, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


class TradingRiskPrefs(FrozenModel):
    total_capital: float | None = Field(description="总资金")
    stop_loss_pct: float = Field(description="止损比例")
    caution_float_pct: float = Field(description="浮亏警戒比例")
    realized_pnl_today: float | None = Field(description="当日已实现盈亏")

    def normalized(self) -> TradingRiskPrefs:
        stop_loss = self.stop_loss_pct
        if stop_loss <= 0 or stop_loss > 0.5:
            stop_loss = DEFAULT_STOP_LOSS_PCT
        total = self.total_capital
        if total is not None and total <= 0:
            total = None
        caution = self.caution_float_pct
        if caution >= 0:
            caution = DEFAULT_CAUTION_FLOAT_PCT
        return TradingRiskPrefs(
            total_capital=total,
            stop_loss_pct=stop_loss,
            caution_float_pct=caution,
            realized_pnl_today=self.realized_pnl_today,
        )


def load_trading_risk_prefs() -> TradingRiskPrefs:
    settings = get_settings()
    return TradingRiskPrefs(
        total_capital=_coerce_float(settings.value(f"{PREFIX}/total_capital")),
        stop_loss_pct=_coerce_float(
            settings.value(f"{PREFIX}/stop_loss_pct"),
            default=DEFAULT_STOP_LOSS_PCT,
        )
        or DEFAULT_STOP_LOSS_PCT,
        caution_float_pct=_coerce_float(
            settings.value(f"{PREFIX}/caution_float_pct"),
            default=DEFAULT_CAUTION_FLOAT_PCT,
        )
        or DEFAULT_CAUTION_FLOAT_PCT,
        realized_pnl_today=_coerce_float(settings.value(f"{PREFIX}/realized_pnl_today")),
    ).normalized()


def save_trading_risk_prefs(prefs: TradingRiskPrefs) -> None:
    item = prefs.normalized()
    settings = get_settings()
    settings.setValue(f"{PREFIX}/total_capital", "" if item.total_capital is None else item.total_capital)
    settings.setValue(f"{PREFIX}/stop_loss_pct", item.stop_loss_pct)
    settings.setValue(f"{PREFIX}/caution_float_pct", item.caution_float_pct)
    settings.setValue(
        f"{PREFIX}/realized_pnl_today",
        "" if item.realized_pnl_today is None else item.realized_pnl_today,
    )
    settings.sync()
