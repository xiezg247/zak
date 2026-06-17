"""交易纪律上下文（AI / 自选页 extra）。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from vnpy_ashare.storage.repositories.trade_journal import count_trade_journal_for_date
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan
from vnpy_ashare.trading.journal.float_loss_hold import scan_float_loss_holds
from vnpy_ashare.trading.journal.plan_check import check_buy_against_plan
from vnpy_ashare.trading.journal.report import load_journal_report
from vnpy_ashare.trading.risk.combined import load_combined_risk_gate_snapshot
from vnpy_ashare.trading.risk.realized_pnl import resolve_realized_pnl_today, today_trade_date

if TYPE_CHECKING:
    from vnpy_ashare.domain.position_snapshot import PositionSnapshot


def build_trading_discipline_snapshot(
    *,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
    trade_date: str | None = None,
) -> dict[str, Any]:
    day = (trade_date or today_trade_date())[:10]
    plan = load_active_trading_plan(day)
    journal_count = count_trade_journal_for_date(day)
    report = load_journal_report(start_date=day, end_date=day)
    effective, journal_total, manual = resolve_realized_pnl_today(day)
    float_holds = scan_float_loss_holds(position_cache)
    combined = load_combined_risk_gate_snapshot(position_cache=position_cache)

    plan_summary = None
    if plan is not None:
        plan_summary = {
            "trade_date": plan.trade_date,
            "max_position_pct": plan.max_position_pct,
            "watchlist": list(plan.watchlist_vt_symbols),
            "status": plan.status,
        }

    return {
        "trade_date": day,
        "trading_plan_summary": plan_summary,
        "journal_today_count": journal_count,
        "journal_violation_count": report.violation_count,
        "float_loss_holds": float_holds,
        "realized_pnl_today": effective,
        "realized_pnl_journal": journal_total,
        "realized_pnl_manual": manual,
        "risk_gate_state": combined.account.state,
        "allow_new_positions": combined.allow_new_positions,
    }


def format_trading_discipline_extra(
    *,
    position_cache: Mapping[str, PositionSnapshot] | None = None,
    vt_symbol: str | None = None,
    trade_date: str | None = None,
) -> str:
    snap_data = build_trading_discipline_snapshot(position_cache=position_cache, trade_date=trade_date)
    lines: list[str] = ["【交易纪律上下文】"]
    plan = snap_data.get("trading_plan_summary")
    if isinstance(plan, dict):
        watchlist = plan.get("watchlist") or []
        max_pct = plan.get("max_position_pct")
        pct_text = f"{int(float(max_pct) * 100)}%" if max_pct is not None else "—"
        lines.append(f"- 激活计划：{plan.get('trade_date')} 仓位≤{pct_text} 观察 {len(watchlist)} 只")
        if watchlist:
            lines.append(f"  名单：{', '.join(str(x) for x in watchlist[:5])}")
    else:
        lines.append("- 激活计划：无（登记 off_plan 仅在存在计划时标记）")

    lines.append(f"- 今日流水：{snap_data.get('journal_today_count')} 条，违规 {snap_data.get('journal_violation_count')} 条")
    float_holds = snap_data.get("float_loss_holds") or []
    if float_holds:
        lines.append(f"- 浮亏扛单：{', '.join(str(x) for x in float_holds)}")

    realized = snap_data.get("realized_pnl_today")
    if realized is not None:
        lines.append(f"- 今日已实现：{float(realized):+.2f} 元")

    lines.append(f"- 风控闸：{snap_data.get('risk_gate_state')} ({'可新开仓' if snap_data.get('allow_new_positions') else '不建议新开仓'})")

    if vt_symbol and position_cache is not None:
        item_snap = position_cache.get(vt_symbol)
        if item_snap is not None:
            symbol, exchange_name = vt_symbol.split(".", 1)
            from vnpy.trader.constant import Exchange

            try:
                exchange = Exchange(exchange_name)
            except ValueError:
                exchange = None
            if exchange is not None:
                day = str(snap_data.get("trade_date") or today_trade_date())[:10]
                check = check_buy_against_plan(symbol, exchange, trade_date=day)
                if check.violation_tags:
                    lines.append(f"- 当前标的违规标签：{', '.join(check.violation_tags)}")
                elif plan is not None:
                    lines.append("- 当前标的：在计划观察名单内" if check.on_plan else "- 当前标的：不在计划名单")

    return "\n".join(lines)


def check_symbol_off_plan_hint(vt_symbol: str, *, trade_date: str | None = None) -> str | None:
    parts = vt_symbol.split(".", 1)
    if len(parts) != 2:
        return None
    from vnpy.trader.constant import Exchange

    try:
        exchange = Exchange(parts[1])
    except ValueError:
        return None
    check = check_buy_against_plan(parts[0], exchange, trade_date=trade_date or today_trade_date())
    if "off_plan" in check.violation_tags:
        return "计划外标的（off_plan）"
    if check.violation_tags:
        return f"违规：{', '.join(check.violation_tags)}"
    return None
