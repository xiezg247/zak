"""当日已实现盈亏：流水汇总 + 手动调整（K-03）。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.storage.repositories.trade_journal import sum_realized_pnl_for_date


def today_trade_date() -> str:
    return datetime.now(CHINA_TZ).date().isoformat()


def resolve_realized_pnl_today(trade_date: str | None = None) -> tuple[float | None, float, float | None]:
    """返回 (合计, 流水汇总, 手动调整)。"""
    day = (trade_date or today_trade_date())[:10]
    journal_total = sum_realized_pnl_for_date(day)
    prefs = load_trading_risk_prefs()
    manual = prefs.realized_pnl_today
    if journal_total == 0.0 and manual is None:
        return None, 0.0, None
    manual_part = manual or 0.0
    return round(journal_total + manual_part, 2), journal_total, manual


def format_realized_pnl_hint(
    *,
    journal_total: float,
    manual: float | None,
    effective: float | None,
) -> str | None:
    if effective is None and journal_total == 0.0 and manual is None:
        return None
    parts: list[str] = []
    if journal_total != 0.0:
        parts.append(f"登记卖出 {journal_total:+.0f}")
    if manual is not None and manual != 0.0:
        parts.append(f"额外 {manual:+.0f}")
    if effective is not None:
        parts.append(f"合计 {effective:+.0f}")
    return " · ".join(parts) if parts else None
