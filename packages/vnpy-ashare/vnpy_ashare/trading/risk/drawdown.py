"""周期回撤追踪与定时熔断（K-04 Phase 3）。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.trading_risk import (
    TradingRiskPrefs,
    load_trading_risk_prefs,
    save_trading_risk_prefs,
)
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.storage.repositories.trade_journal import sum_realized_pnl_all

if TYPE_CHECKING:
    from vnpy_ashare.domain.trading.position import PositionSnapshot

DEFAULT_CAUTION_WEEKLY_DRAWDOWN_PCT = -5.0
DEFAULT_HALT_TOTAL_DRAWDOWN_PCT = -10.0
WEEKLY_HALT_DAYS = 2
TOTAL_HALT_DAYS = 7


def _today() -> date:
    return datetime.now(CHINA_TZ).date()


def _iso_week_key(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def compute_current_equity(
    *,
    total_capital: float,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
) -> float:
    """当前权益 ≈ 总资金 + 累计已实现 + 当前浮动盈亏。"""
    float_pnl = 0.0
    if position_cache:
        for snap in position_cache.values():
            if snap.unrealized_pnl is not None:
                float_pnl += float(snap.unrealized_pnl)
    realized_all = sum_realized_pnl_all()
    return round(total_capital + realized_all + float_pnl, 2)


def _drawdown_pct(current: float, peak: float) -> float | None:
    if peak <= 0:
        return None
    return round((current - peak) / peak * 100, 2)


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_halt_active(prefs: TradingRiskPrefs, *, today: date | None = None) -> bool:
    day = today or _today()
    until = _parse_date(prefs.halt_until)
    return until is not None and day <= until


def _is_halt_active(prefs: TradingRiskPrefs, *, today: date | None = None) -> bool:
    return is_halt_active(prefs, today=today)


def update_drawdown_tracking(
    prefs: TradingRiskPrefs,
    *,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
) -> TradingRiskPrefs:
    """刷新峰值权益并评估是否触发周期熔断。"""
    if prefs.total_capital is None or prefs.total_capital <= 0:
        return prefs

    today = _today()
    current = compute_current_equity(total_capital=prefs.total_capital, position_cache=position_cache)
    peak = prefs.peak_equity if prefs.peak_equity is not None and prefs.peak_equity > 0 else current
    if current > peak:
        peak = current

    week_key = _iso_week_key(today)
    week_peak = prefs.week_peak_equity
    if prefs.week_peak_key != week_key or week_peak is None or week_peak <= 0:
        week_peak = current
    elif current > week_peak:
        week_peak = current

    halt_until = prefs.halt_until
    halt_reason = prefs.halt_reason
    total_dd = _drawdown_pct(current, peak)
    weekly_dd = _drawdown_pct(current, week_peak)

    if total_dd is not None and total_dd <= DEFAULT_HALT_TOTAL_DRAWDOWN_PCT:
        until = today + timedelta(days=TOTAL_HALT_DAYS)
        halt_until = until.isoformat()
        halt_reason = "total_drawdown"
    elif weekly_dd is not None and weekly_dd <= DEFAULT_CAUTION_WEEKLY_DRAWDOWN_PCT:
        until = today + timedelta(days=WEEKLY_HALT_DAYS)
        if halt_reason != "total_drawdown":
            halt_until = until.isoformat()
            halt_reason = "weekly_drawdown"

    return prefs.model_copy(
        update={
            "peak_equity": peak,
            "week_peak_equity": week_peak,
            "week_peak_key": week_key,
            "halt_until": halt_until,
            "halt_reason": halt_reason,
        },
    )


def evaluate_drawdown(
    prefs: TradingRiskPrefs,
    *,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
    persist: bool = True,
) -> tuple[TradingRiskPrefs, float | None, float | None, list[str]]:
    """评估回撤并可选持久化峰值/熔断状态。"""
    warnings: list[str] = []
    if prefs.total_capital is None or prefs.total_capital <= 0:
        return prefs, None, None, warnings

    updated = update_drawdown_tracking(prefs, position_cache=position_cache)
    if persist and updated != prefs:
        save_trading_risk_prefs(updated)

    today = _today()
    if _is_halt_active(updated, today=today):
        until = _parse_date(updated.halt_until)
        reason = updated.halt_reason or "drawdown"
        label = "总回撤" if reason == "total_drawdown" else "单周回撤"
        until_text = until.isoformat() if until is not None else "—"
        warnings.append(f"{label}熔断中，停手至 {until_text}")

    current = compute_current_equity(total_capital=updated.total_capital, position_cache=position_cache)
    peak = updated.peak_equity or current
    week_peak = updated.week_peak_equity or current
    total_dd = _drawdown_pct(current, peak)
    weekly_dd = _drawdown_pct(current, week_peak)

    if total_dd is not None and total_dd < 0 and not _is_halt_active(updated, today=today):
        warnings.append(f"总回撤 {total_dd:.1f}%（峰值 {peak:,.0f} 元）")
    if weekly_dd is not None and weekly_dd < 0:
        warnings.append(f"单周回撤 {weekly_dd:.1f}%")

    return updated, weekly_dd, total_dd, warnings


def reset_peak_equity(*, total_capital: float | None = None) -> None:
    """重置峰值权益（用户手动校准）。"""
    prefs = load_trading_risk_prefs()
    capital = total_capital if total_capital is not None and total_capital > 0 else prefs.total_capital
    if capital is None or capital <= 0:
        save_trading_risk_prefs(
            prefs.model_copy(
                update={
                    "peak_equity": None,
                    "week_peak_equity": None,
                    "week_peak_key": "",
                    "halt_until": None,
                    "halt_reason": "",
                },
            ),
        )
        return
    today = _today()
    save_trading_risk_prefs(
        prefs.model_copy(
            update={
                "peak_equity": capital,
                "week_peak_equity": capital,
                "week_peak_key": _iso_week_key(today),
                "halt_until": None,
                "halt_reason": "",
            },
        ),
    )


def clear_timed_halt() -> None:
    """清除定时熔断（手动解除）。"""
    prefs = load_trading_risk_prefs()
    if not prefs.halt_until:
        return
    save_trading_risk_prefs(
        prefs.model_copy(update={"halt_until": None, "halt_reason": ""}),
    )
