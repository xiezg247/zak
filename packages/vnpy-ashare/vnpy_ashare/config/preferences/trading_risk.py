"""交易风控 QSettings（K-01）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings
from vnpy_common.domain.base import FrozenModel

PREFIX = "trading/risk"

DEFAULT_PER_TRADE_RISK_PCT = 0.02
DEFAULT_STOP_LOSS_PCT = 0.05
DEFAULT_CAUTION_DAILY_PCT = -3.0
DEFAULT_HALT_DAILY_PCT = -5.0
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
    per_trade_risk_pct: float = Field(description="单笔风险占比")
    stop_loss_pct: float = Field(description="止损比例")
    daily_pnl_pct: float | None = Field(description="当日盈亏比例")
    realized_pnl_today: float | None = Field(description="当日已实现盈亏")
    caution_daily_pct: float = Field(description="日亏警戒比例")
    halt_daily_pct: float = Field(description="日亏熔断比例")
    caution_float_pct: float = Field(description="浮亏警戒比例")
    manual_halt: bool = Field(description="是否手动熔断")

    def normalized(self) -> TradingRiskPrefs:
        per_trade = self.per_trade_risk_pct
        if per_trade <= 0 or per_trade > 0.5:
            per_trade = DEFAULT_PER_TRADE_RISK_PCT
        stop_loss = self.stop_loss_pct
        if stop_loss <= 0 or stop_loss > 0.5:
            stop_loss = DEFAULT_STOP_LOSS_PCT
        total = self.total_capital
        if total is not None and total <= 0:
            total = None
        return TradingRiskPrefs(
            total_capital=total,
            per_trade_risk_pct=per_trade,
            stop_loss_pct=stop_loss,
            daily_pnl_pct=self.daily_pnl_pct,
            realized_pnl_today=self.realized_pnl_today,
            caution_daily_pct=self.caution_daily_pct,
            halt_daily_pct=self.halt_daily_pct,
            caution_float_pct=self.caution_float_pct,
            manual_halt=self.manual_halt,
        )


def load_trading_risk_prefs() -> TradingRiskPrefs:
    settings = get_settings()
    return TradingRiskPrefs(
        total_capital=_coerce_float(settings.value(f"{PREFIX}/total_capital")),
        per_trade_risk_pct=_coerce_float(
            settings.value(f"{PREFIX}/per_trade_risk_pct"),
            default=DEFAULT_PER_TRADE_RISK_PCT,
        )
        or DEFAULT_PER_TRADE_RISK_PCT,
        stop_loss_pct=_coerce_float(
            settings.value(f"{PREFIX}/stop_loss_pct"),
            default=DEFAULT_STOP_LOSS_PCT,
        )
        or DEFAULT_STOP_LOSS_PCT,
        daily_pnl_pct=_coerce_float(settings.value(f"{PREFIX}/daily_pnl_pct")),
        realized_pnl_today=_coerce_float(settings.value(f"{PREFIX}/realized_pnl_today")),
        caution_daily_pct=_coerce_float(
            settings.value(f"{PREFIX}/caution_daily_pct"),
            default=DEFAULT_CAUTION_DAILY_PCT,
        )
        or DEFAULT_CAUTION_DAILY_PCT,
        halt_daily_pct=_coerce_float(
            settings.value(f"{PREFIX}/halt_daily_pct"),
            default=DEFAULT_HALT_DAILY_PCT,
        )
        or DEFAULT_HALT_DAILY_PCT,
        caution_float_pct=_coerce_float(
            settings.value(f"{PREFIX}/caution_float_pct"),
            default=DEFAULT_CAUTION_FLOAT_PCT,
        )
        or DEFAULT_CAUTION_FLOAT_PCT,
        manual_halt=coerce_settings_bool(settings.value(f"{PREFIX}/manual_halt"), default=False),
    ).normalized()


def save_trading_risk_prefs(prefs: TradingRiskPrefs) -> None:
    item = prefs.normalized()
    settings = get_settings()
    if item.total_capital is None:
        settings.remove(f"{PREFIX}/total_capital")
    else:
        settings.setValue(f"{PREFIX}/total_capital", item.total_capital)
    settings.setValue(f"{PREFIX}/per_trade_risk_pct", item.per_trade_risk_pct)
    settings.setValue(f"{PREFIX}/stop_loss_pct", item.stop_loss_pct)
    if item.daily_pnl_pct is None:
        settings.remove(f"{PREFIX}/daily_pnl_pct")
    else:
        settings.setValue(f"{PREFIX}/daily_pnl_pct", item.daily_pnl_pct)
    if item.realized_pnl_today is None:
        settings.remove(f"{PREFIX}/realized_pnl_today")
    else:
        settings.setValue(f"{PREFIX}/realized_pnl_today", item.realized_pnl_today)
    settings.setValue(f"{PREFIX}/caution_daily_pct", item.caution_daily_pct)
    settings.setValue(f"{PREFIX}/halt_daily_pct", item.halt_daily_pct)
    settings.setValue(f"{PREFIX}/caution_float_pct", item.caution_float_pct)
    settings.setValue(f"{PREFIX}/manual_halt", int(item.manual_halt))
