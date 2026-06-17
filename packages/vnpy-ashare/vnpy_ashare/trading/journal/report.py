"""交易流水复盘报表（J-05）。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.journal import TradeJournalEntry
from vnpy_ashare.domain.trading.journal_report import JournalReport
from vnpy_ashare.storage.repositories.trade_journal import query_trade_journal

__all__ = ["JournalReport", "build_journal_report", "load_journal_report"]


def build_journal_report(
    entries: list[TradeJournalEntry],
) -> JournalReport:
    total = len(entries)
    buy_count = sum(1 for item in entries if item.side == "buy")
    sell_count = sum(1 for item in entries if item.side == "sell")
    on_plan_count = sum(1 for item in entries if item.on_plan)
    violation_count = sum(1 for item in entries if item.violation_tags)
    off_plan_count = sum(1 for item in entries if "off_plan" in item.violation_tags)
    add_loss_count = sum(1 for item in entries if "add_loss" in item.violation_tags)
    float_loss_hold_count = sum(1 for item in entries if "float_loss_hold" in item.violation_tags)

    sell_pnls = [item.pnl for item in entries if item.side == "sell" and item.pnl is not None]
    wins = [value for value in sell_pnls if value > 0]
    losses = [value for value in sell_pnls if value < 0]
    win_count = len(wins)
    loss_count = len(losses)
    closed = win_count + loss_count
    win_rate = round(win_count / closed * 100, 2) if closed else None
    avg_win = round(sum(wins) / len(wins), 2) if wins else None
    avg_loss = round(sum(losses) / len(losses), 2) if losses else None
    pl_ratio = None
    if avg_win is not None and avg_loss is not None and avg_loss < 0:
        pl_ratio = round(avg_win / abs(avg_loss), 2)
    on_plan_ratio = round(on_plan_count / total * 100, 2) if total else None
    violation_ratio = round(violation_count / total * 100, 2) if total else None
    realized_total = round(sum(sell_pnls), 2) if sell_pnls else 0.0

    return JournalReport(
        total_entries=total,
        buy_count=buy_count,
        sell_count=sell_count,
        on_plan_count=on_plan_count,
        violation_count=violation_count,
        off_plan_count=off_plan_count,
        add_loss_count=add_loss_count,
        float_loss_hold_count=float_loss_hold_count,
        win_count=win_count,
        loss_count=loss_count,
        win_rate_pct=win_rate,
        profit_loss_ratio=pl_ratio,
        on_plan_ratio_pct=on_plan_ratio,
        violation_ratio_pct=violation_ratio,
        realized_pnl_total=realized_total,
        avg_win=avg_win,
        avg_loss=avg_loss,
    )


def load_journal_report(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 500,
) -> JournalReport:
    entries = query_trade_journal(start_date=start_date, end_date=end_date, limit=limit)
    return build_journal_report(entries)


def format_journal_entries_csv(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 5000,
) -> str:
    entries = query_trade_journal(start_date=start_date, end_date=end_date, limit=limit)
    header = "trade_date,symbol,exchange,side,price,volume,amount,on_plan,violation_tags,pnl,pnl_pct,emotion_stage,reason,mode,plan_id,created_at"
    lines = [header]
    for item in entries:
        tags = "|".join(item.violation_tags)
        pnl = "" if item.pnl is None else f"{item.pnl:.2f}"
        pnl_pct = "" if item.pnl_pct is None else f"{item.pnl_pct:.4f}"
        row = (
            f"{item.trade_date},{item.symbol},{item.exchange},{item.side},"
            f"{item.price:.4f},{item.volume},{item.amount:.2f},"
            f"{'1' if item.on_plan else '0'},"
            f'"{tags}",{pnl},{pnl_pct},'
            f'{item.emotion_stage},"{item.reason.replace(chr(34), chr(39))}",'
            f"{item.mode},{item.plan_id or ''},{item.created_at}"
        )
        lines.append(row)
    return "\n".join(lines) + "\n"


def format_journal_report_hint(report: JournalReport) -> str | None:
    if report.total_entries <= 0:
        return None
    parts = [f"流水 {report.total_entries}"]
    if report.win_rate_pct is not None:
        parts.append(f"胜率 {report.win_rate_pct:.0f}%")
    if report.profit_loss_ratio is not None:
        parts.append(f"盈亏比 {report.profit_loss_ratio:.1f}")
    if report.violation_count:
        parts.append(f"违规 {report.violation_count}")
    if report.realized_pnl_total:
        parts.append(f"已实现 {report.realized_pnl_total:+.0f}")
    return " · ".join(parts)
