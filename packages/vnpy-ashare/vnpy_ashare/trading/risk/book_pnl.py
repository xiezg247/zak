"""记账盈亏汇总（K-03 MVP）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel

from collections.abc import Mapping
from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.trading.risk.combined import compute_avg_float_pnl_pct
from vnpy_ashare.trading.risk.realized_pnl import resolve_realized_pnl_today, today_trade_date

if TYPE_CHECKING:
    from vnpy_ashare.domain.trading.position import PositionSnapshot


class BookPnlSummary(FrozenModel):
    total_float_pnl: float = Field(description="浮动盈亏合计")
    position_count: int = Field(description="持仓数量")
    total_float_pnl_pct: float | None = Field(description="浮动盈亏占比（%）")
    avg_float_pnl_pct: float | None = Field(description="持仓平均浮盈占比（%）")
    realized_pnl_today: float | None = Field(description="当日已实现盈亏")
    realized_pnl_journal: float | None = Field(description="登记已实现盈亏")
    realized_pnl_manual: float | None = Field(description="手动录入已实现盈亏")
    combined_pnl_amount: float | None = Field(description="合计盈亏金额")
    combined_pnl_pct: float | None = Field(description="合计盈亏占比（%）")


def summarize_book_pnl(
    position_cache: Mapping[str, PositionSnapshot] | None,
) -> BookPnlSummary:
    prefs = load_trading_risk_prefs()
    total_float = 0.0
    count = 0
    has_float = False
    if position_cache:
        for snap in position_cache.values():
            if snap.unrealized_pnl is None:
                continue
            total_float += float(snap.unrealized_pnl)
            has_float = True
            count += 1

    avg_pct = compute_avg_float_pnl_pct(position_cache)
    float_pct = None
    if prefs.total_capital is not None and prefs.total_capital > 0 and has_float:
        float_pct = round(total_float / prefs.total_capital * 100, 2)

    realized = prefs.realized_pnl_today
    effective, journal_total, manual = resolve_realized_pnl_today(today_trade_date())
    if effective is not None:
        realized = effective
    combined_amount: float | None = None
    combined_pct: float | None = None
    if has_float or realized is not None:
        combined_amount = round(total_float + (realized or 0.0), 2)
    if prefs.total_capital is not None and prefs.total_capital > 0 and combined_amount is not None:
        combined_pct = round(combined_amount / prefs.total_capital * 100, 2)

    return BookPnlSummary(
        total_float_pnl=round(total_float, 2) if has_float else 0.0,
        position_count=count,
        total_float_pnl_pct=float_pct,
        avg_float_pnl_pct=round(avg_pct, 2) if avg_pct is not None else None,
        realized_pnl_today=realized,
        realized_pnl_journal=journal_total if journal_total != 0.0 else None,
        realized_pnl_manual=manual,
        combined_pnl_amount=combined_amount,
        combined_pnl_pct=combined_pct,
    )


def format_book_pnl_hint(summary: BookPnlSummary) -> str | None:
    if summary.position_count <= 0 and summary.realized_pnl_today is None:
        return None
    parts: list[str] = []
    if summary.position_count > 0:
        parts.append(f"浮盈 {summary.total_float_pnl:+.2f}")
    if summary.realized_pnl_today is not None:
        if summary.realized_pnl_journal is not None and summary.realized_pnl_manual not in (None, 0.0):
            parts.append(f"已实现 {summary.realized_pnl_today:+.2f}（登记 {summary.realized_pnl_journal:+.0f}+额外 {summary.realized_pnl_manual:+.0f}）")
        elif summary.realized_pnl_journal is not None:
            parts.append(f"已实现 {summary.realized_pnl_today:+.2f}（登记卖出）")
        else:
            parts.append(f"已实现 {summary.realized_pnl_today:+.2f}")
    if summary.combined_pnl_pct is not None:
        parts.append(f"合计 {summary.combined_pnl_pct:+.1f}%")
    elif summary.total_float_pnl_pct is not None:
        parts.append(f"浮盈占比 {summary.total_float_pnl_pct:+.1f}%")
    return " · ".join(parts) if parts else None
