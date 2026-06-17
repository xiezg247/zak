"""盘后复盘 Prompt 预填（J-03 / AI）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.storage.repositories.trade_journal import query_trade_journal
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan
from vnpy_ashare.trading.journal.float_loss_hold import scan_float_loss_holds
from vnpy_ashare.trading.journal.report import load_journal_report
from vnpy_ashare.trading.risk.realized_pnl import resolve_realized_pnl_today


def build_journal_prompt(
    *,
    position_cache=None,
    days: int = 1,
) -> dict[str, object]:
    end = datetime.now(CHINA_TZ).date()
    start = end - timedelta(days=max(0, days - 1))
    start_text = start.isoformat()
    end_text = end.isoformat()

    report = load_journal_report(start_date=start_text, end_date=end_text)
    entries = query_trade_journal(start_date=start_text, end_date=end_text, limit=50)
    plan = load_active_trading_plan(end_text)
    emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    effective, journal_total, manual = resolve_realized_pnl_today(end_text)
    float_holds = scan_float_loss_holds(position_cache)

    lines = [
        f"复盘区间：{start_text} ~ {end_text}",
        "",
        "## 市场 / 情绪",
    ]
    if emotion is not None:
        lines.append(f"- 情绪阶段：{emotion.stage_label}（{emotion.stage}）")
        lines.append(f"- 建议仓位：≤{int(emotion.position_pct_max * 100)}%")
    else:
        lines.append("- 情绪阶段：暂无")

    lines.extend(["", "## 计划执行"])
    if plan is not None:
        lines.append(f"- 激活计划日：{plan.trade_date}")
        lines.append(f"- 观察名单：{', '.join(plan.watchlist_vt_symbols) or '（空）'}")
    else:
        lines.append("- 当日无激活交易计划")

    lines.extend(["", "## 流水统计"])
    lines.append(f"- 流水条数：{report.total_entries}（买 {report.buy_count} / 卖 {report.sell_count}）")
    if report.win_rate_pct is not None:
        lines.append(f"- 胜率：{report.win_rate_pct:.1f}%")
    if report.profit_loss_ratio is not None:
        lines.append(f"- 盈亏比：{report.profit_loss_ratio:.2f}")
    lines.append(f"- 违规笔数：{report.violation_count}（off_plan {report.off_plan_count}）")
    if effective is not None:
        lines.append(f"- 已实现：{effective:+.2f} 元（登记卖出 {journal_total:+.2f}）")

    if float_holds:
        lines.extend(["", "## 浮亏扛单（待处理）", f"- {', '.join(float_holds)}"])

    if entries:
        lines.extend(["", "## 流水明细"])
        for item in entries[:15]:
            tags = f" [{','.join(item.violation_tags)}]" if item.violation_tags else ""
            pnl = f" pnl={item.pnl:+.0f}" if item.pnl is not None else ""
            lines.append(f"- {item.trade_date} {item.side} {item.vt_symbol} @{item.price:.2f} x{item.volume}{pnl}{tags}")

    prompt = "\n".join(lines)
    return {
        "start_date": start_text,
        "end_date": end_text,
        "prompt": prompt,
        "report": report.to_dict(),
        "float_loss_holds": float_holds,
        "plan_active": plan is not None,
    }
