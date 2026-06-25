"""策略回测页 AI 上下文组装。

读取链路：BacktestService.get_last_summary → 回退 context_store.get_backtest_summary_dict。
写入经 set_ai_context，与 QuoteService / ScreeningService 共用同一 store。
"""

from __future__ import annotations

from typing import Any, cast

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ai.context.store import get_backtest_summary_dict, set_ai_context
from vnpy_ashare.app.engine_access import get_service
from vnpy_common.ai.protocol import AiContextData, QuickAction


def resolve_backtest_summary(main_engine=None) -> dict[str, Any] | None:
    """优先从 BacktestService 读取，回退 session 缓存。"""
    service = get_service(main_engine, "backtest_service")
    if service is not None:
        summary = service.get_last_summary()
        if summary:
            return cast(dict[str, Any], summary)
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
    strategy = ""
    if class_combo is not None:
        display_title = getattr(class_combo, "current_display_title", None)
        strategy = (display_title() if callable(display_title) else class_combo.currentText()).strip()
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
    return f"请解读最近一次回测（策略 {strategy} · 标的 {vt_symbol}）。获取摘要指标后结合上下文解读，不要编造未在结果中的数值。"


def build_backtest_page_quick_actions(*, main_engine=None) -> list[QuickAction]:
    """策略回测页快捷动作。"""
    summary = resolve_backtest_summary(main_engine)
    interpret_prompt = (
        build_backtest_ai_prompt(summary)
        if summary
        else "请解读最近一次回测结果。若尚无回测，请先运行回测后再解读，不要编造指标。"
    )
    return [
        QuickAction(
            id="interpret_backtest",
            label="解读回测",
            tooltip="解读最近回测摘要指标",
            prompt=interpret_prompt,
        ),
        QuickAction(
            id="backtest_param_hint",
            label="参数建议",
            tooltip="基于表单与摘要给出可调参方向（需再回测验证）",
            prompt=(
                "基于当前回测表单与最近回测摘要，给出参数调优方向（如均线窗口、持仓周期、止损），"
                "说明需再回测验证，不要编造收益数字。"
            ),
        ),
        QuickAction(
            id="backtest_risk_review",
            label="回撤与交易",
            tooltip="聚焦最大回撤、胜率与交易次数",
            prompt=(
                "请聚焦最近一次回测的最大回撤、夏普、交易次数与胜率，"
                "分析策略风险特征与是否过拟合，不要编造未在摘要中的数值。"
            ),
        ),
    ]


def build_batch_compare_quick_actions() -> list[QuickAction]:
    """批量回测对比页快捷动作。"""
    return [
        QuickAction(
            id="interpret_batch_compare",
            label="批次解读",
            tooltip="解读批量回测收益/夏普分布",
            prompt=(
                "请解读当前批量回测对比批次：收益与夏普分布、成功率、"
                "最优与最差标的差异，不要编造未在摘要中的数据。"
            ),
        ),
        QuickAction(
            id="batch_attribution",
            label="最优最差归因",
            tooltip="对比批次内最优与最差标的",
            prompt=(
                "请针对批量回测中最优与最差标的做归因对比（区间行情、策略信号差异），"
                "不要编造未在摘要中的数据。"
            ),
        ),
    ]


def sync_backtest_page_context(widget: QtWidgets.QWidget, main_engine=None, *, notify_ui: bool = True) -> None:
    """组装回测页上下文并写入 context_store（含快捷动作 enrichment）。"""
    from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions

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
    from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions

    data = enrich_context_with_actions(build_batch_compare_context(session, rows))
    set_ai_context(data)
