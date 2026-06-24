"""当日已实现盈亏（手动录入）。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.domain.time.market_hours import CHINA_TZ


def today_trade_date() -> str:
    return datetime.now(CHINA_TZ).date().isoformat()


def resolve_realized_pnl_today() -> float | None:
    """返回当日手动录入的已实现盈亏；无录入时为 None。"""
    return load_trading_risk_prefs().realized_pnl_today
