"""对话进行中占位气泡文案。"""

from __future__ import annotations

from vnpy_llm.tool_labels import tool_display_name
from vnpy_llm.trace import TraceStep, TurnTrace

SPINNER_FRAMES = ("◌", "○", "●", "○")


def pending_status_from_turn(turn: TurnTrace | None) -> tuple[str, str]:
    """根据当前 Trace 轮次生成 (主文案, 副文案)。"""
    if turn is None:
        return "思考中…", "已收到你的问题"

    running_tools = [s for s in turn.steps if s.kind == "tool" and s.status == "running"]
    done_tools = [s for s in turn.steps if s.kind == "tool" and s.status == "ok"]
    reply_running = any(s.kind == "reply" and s.status == "running" for s in turn.steps)
    has_routing = any(s.kind == "routing" for s in turn.steps)
    has_error = any(s.kind == "error" for s in turn.steps)

    if has_error:
        err = next(s for s in turn.steps if s.kind == "error")
        return "处理遇到问题", err.summary or "请稍后重试"

    if running_tools:
        main = _tool_running_text(running_tools)
        done_count = len(done_tools)
        sub = f"已完成 {done_count} 项" if done_count else "数据查询中，请稍候"
        return main, sub

    if reply_running:
        return "整理结论…", "正在生成回复"

    if has_routing:
        return "理解意图，准备查询…", "分析完成，即将调用工具"

    return "思考中…", "理解你的问题"


def _tool_running_text(running: list[TraceStep]) -> str:
    if len(running) == 1:
        return f"正在{tool_display_name(running[0].name)}…"
    names = "、".join(tool_display_name(s.name) for s in running[:2])
    if len(running) > 2:
        names += f" 等 {len(running)} 项"
    return f"正在并行查询：{names}…"


def format_pending_html(
    main: str,
    sub: str,
    *,
    spinner: str = SPINNER_FRAMES[0],
) -> str:
    from vnpy_common.ui.theme import theme_manager
    from vnpy_common.ui.theme.html_palette import html_palette

    sub_html = ""
    if sub.strip():
        sub_color = html_palette(theme_manager().tokens()).label
        sub_html = f'<br><span style="color:{sub_color};font-size:11px;">{sub}</span>'
    return f"{spinner} {main}{sub_html}"
