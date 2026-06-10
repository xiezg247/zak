"""策略回测页 AI 上下文组装。

读取链路：BacktestService.get_last_summary → 回退 context_store.get_backtest_summary_dict。
写入经 set_ai_context，与 QuoteService / ScreeningService 共用同一 store。
"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.context_store import get_backtest_summary_dict, set_ai_context
from vnpy_ashare.ai.floating_actions import enrich_context_with_actions
from vnpy_ashare.app.engine_access import get_service


def resolve_backtest_summary(main_engine=None) -> dict[str, Any] | None:
    """优先从 BacktestService 读取，回退 session 缓存。"""
    service = get_service(main_engine, "backtest_service")
    if service is not None:
        summary = service.get_last_summary()
        if summary:
            return summary
    return get_backtest_summary_dict()


def _fmt_metric(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        text = str(value).replace("%", "").strip()
        return f"{float(text):.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_backtest_summary_text(summary: dict[str, Any] | None) -> str:
    """将回测摘要 dict 格式化为多行可读文本。"""
    if not summary:
        return "最近回测：尚未完成回测"
    stats = dict(summary.get("statistics") or {})
    lines = [
        "最近回测摘要：",
        f"  策略：{summary.get('strategy', '—')}",
        f"  标的：{summary.get('vt_symbol', '—')}",
        f"  区间：{summary.get('start', '—')} ~ {summary.get('end', '—')}",
        f"  总收益：{_fmt_metric(stats.get('total_return', summary.get('total_return')))}",
        f"  最大回撤：{_fmt_metric(stats.get('max_drawdown', summary.get('max_drawdown')))}",
        f"  夏普：{_fmt_metric(stats.get('sharpe_ratio', summary.get('sharpe_ratio')))}",
        f"  交易次数：{stats.get('total_trade_count', summary.get('trade_count', '—'))}",
    ]
    return "\n".join(lines)


def build_backtest_page_context(
    widget: QtWidgets.QWidget,
    main_engine=None,
) -> AiContextData:
    """从 BacktesterWidget 表单与最近摘要组装上下文。"""
    symbol_line = getattr(widget, "symbol_line", None)
    class_combo = getattr(widget, "class_combo", None)
    interval_combo = getattr(widget, "interval_combo", None)
    start_edit = getattr(widget, "start_date_edit", None)
    end_edit = getattr(widget, "end_date_edit", None)

    vt_symbol = symbol_line.text().strip() if symbol_line is not None else ""
    strategy = class_combo.currentText().strip() if class_combo is not None else ""
    interval = interval_combo.currentText().strip() if interval_combo is not None else ""

    date_range = ""
    if start_edit is not None and end_edit is not None:
        start = start_edit.dateTime().toString("yyyy-MM-dd")
        end = end_edit.dateTime().toString("yyyy-MM-dd")
        date_range = f"{start} ~ {end}"

    extra_parts = [
        "你正在协助用户解读 A 股策略回测结果；请基于回测摘要与工具数据回答，禁止编造指标。",
        f"当前表单：策略 {strategy or '—'} · 标的 {vt_symbol or '—'} · 周期 {interval or '—'}",
    ]
    if date_range:
        extra_parts.append(f"回测区间：{date_range}")
    extra_parts.append(format_backtest_summary_text(resolve_backtest_summary(main_engine)))

    symbol = vt_symbol.split(".", 1)[0] if "." in vt_symbol else vt_symbol
    exchange = vt_symbol.split(".", 1)[1] if "." in vt_symbol else ""

    return AiContextData(
        page="策略回测",
        symbol=symbol,
        exchange=exchange,
        name=vt_symbol,
        extra="\n".join(extra_parts),
    )


def build_backtest_ai_prompt(summary: dict[str, Any]) -> str:
    """生成跳转 AI 助手页的回测解读预填文案。"""
    strategy = summary.get("strategy", "—")
    vt_symbol = summary.get("vt_symbol", "—")
    return f"请解读最近一次回测（策略 {strategy} · 标的 {vt_symbol}）。请调用 get_backtest_result 获取摘要指标，结合上下文解读，不要编造未在结果中的数值。"


def sync_backtest_page_context(widget: QtWidgets.QWidget, main_engine=None, *, notify_ui: bool = True) -> None:
    """组装回测页上下文并写入 context_store（含快捷动作 enrichment）。"""
    data = enrich_context_with_actions(build_backtest_page_context(widget, main_engine))
    set_ai_context(data)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def build_batch_compare_context(session, rows: list[Any]) -> AiContextData:
    """批量回测对比页 AI 上下文（批次统计 + 最优/最差标的）。"""
    returns = [float(row.total_return) for row in rows if row.total_return is not None]
    sharpes = [float(row.sharpe_ratio) for row in rows if row.sharpe_ratio is not None]
    valid_rows = [row for row in rows if row.total_return is not None]
    best = max(valid_rows, key=lambda r: r.total_return, default=None)
    worst = min(valid_rows, key=lambda r: r.total_return, default=None)

    extra_parts = [
        "你正在协助用户对比批量回测结果；请基于下列统计解读，禁止编造。",
    ]
    if session is not None:
        extra_parts.append(f"当前批次：策略 {session.strategy} · {session.start_date}~{session.end_date} · {session.success_count}/{session.row_count} 成功")
    if returns:
        extra_parts.append(f"总收益：均值 {_avg(returns):.2f} · 最高 {max(returns):.2f} · 最低 {min(returns):.2f}")
    if sharpes:
        extra_parts.append(f"夏普：均值 {_avg(sharpes):.2f}")
    if best is not None and best.total_return is not None:
        extra_parts.append(f"最优：{best.vt_symbol}（收益 {best.total_return:.2f}）")
    if worst is not None and worst.total_return is not None:
        extra_parts.append(f"最差：{worst.vt_symbol}（收益 {worst.total_return:.2f}）")

    return AiContextData(page="回测对比", extra="\n".join(extra_parts))


def sync_batch_compare_context(session, rows: list[Any], main_engine=None) -> None:
    """写入批量回测对比页上下文。"""
    data = enrich_context_with_actions(build_batch_compare_context(session, rows))
    set_ai_context(data)
