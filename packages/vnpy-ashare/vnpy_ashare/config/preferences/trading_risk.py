"""交易参数（总资金、止损、浮亏阈值等）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences._user_pref import load_model_pref, save_model_pref
from vnpy_common.domain.base import FrozenModel

PREFIX = "trading/risk"
_PREF_NAMESPACE = "trading"
_PREF_KEY = "risk"

DEFAULT_STOP_LOSS_PCT = 0.05
DEFAULT_CAUTION_FLOAT_PCT = -5.0

_MIGRATE_KEYS = (
    f"{PREFIX}/total_capital",
    f"{PREFIX}/stop_loss_pct",
    f"{PREFIX}/caution_float_pct",
    f"{PREFIX}/realized_pnl_today",
)


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


def _load_trading_risk_from_qsettings() -> TradingRiskPrefs:
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


def load_trading_risk_prefs() -> TradingRiskPrefs:
    item = load_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        TradingRiskPrefs,
        load_legacy=_load_trading_risk_from_qsettings,
        migrate_keys=_MIGRATE_KEYS,
    )
    return item.normalized()


def save_trading_risk_prefs(prefs: TradingRiskPrefs) -> None:
    save_model_pref(_PREF_NAMESPACE, _PREF_KEY, prefs.normalized())
