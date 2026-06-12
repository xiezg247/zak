"""AI 上下文增强：badge、chip_text、快捷动作（供 Service 写入前调用）。"""

from __future__ import annotations

import re
from dataclasses import replace

from vnpy_ashare.ai.context.quote import (
    build_assistant_quick_actions,
    build_assistant_screening_menus,
    build_floating_stock_quick_actions,
)
from vnpy_ashare.ai.context.store import get_screening_results
from vnpy_common.ai.protocol import AiContextData, QuickAction


def enrich_context_with_actions(data: AiContextData) -> AiContextData:
    """为上下文填充 badge、chip_text、actions。"""
    badge = _build_badge(data)
    chip_text = _build_chip_text(data)
    actions = _build_actions(data)
    return replace(data, badge=badge, chip_text=chip_text, actions=actions)


def build_interpret_screen_action() -> QuickAction | None:
    """最近一次选股/形态扫描结果解读（无结果时返回 None）。"""
    ctx = get_screening_results()
    if ctx is None or ctx.count <= 0:
        return None
    return QuickAction(
        id="interpret_screen",
        label="解读选股结果",
        auto_send=True,
        tooltip=f"解读「{ctx.condition}」共 {ctx.count} 条",
        prompt=(f"请解读选股结果「{ctx.condition}」（共 {ctx.count} 条）。分析板块分布、与上次变动差异及技术面特征后解读，不要编造。"),
    )


def build_screening_quick_actions() -> list[QuickAction]:
    """选股页 / 悬浮球：解读最近结果 + 形态/条件选股菜单。"""
    actions: list[QuickAction] = []
    interpret = build_interpret_screen_action()
    if interpret is not None:
        actions.append(interpret)
    actions.extend(build_assistant_screening_menus())
    return actions


def build_assistant_panel_quick_actions() -> list[QuickAction]:
    """全屏 AI 助手：最近结果解读 + 单票分析 + 全市场选股菜单。"""
    actions: list[QuickAction] = []
    interpret = build_interpret_screen_action()
    if interpret is not None:
        actions.append(interpret)
    actions.extend(build_assistant_quick_actions())
    return actions


def build_page_quick_actions(data: AiContextData) -> list[QuickAction]:
    """按页面类型组装非个股快捷动作。"""
    if data.page == "选股":
        return build_screening_quick_actions()
    if data.page == "数据管理":
        return [
            QuickAction(
                id="data_gap",
                label="检查数据缺口",
                prompt=("请根据当前本地 K 线覆盖情况，分析可能存在的数据缺口，并说明建议优先补全哪些标的或周期。"),
            ),
        ]
    return []


def _build_actions(data: AiContextData) -> list[QuickAction]:
    if data.page in ("自选", "市场", "雷达", "本地") and data.symbol:
        return build_floating_stock_quick_actions(
            data.symbol,
            exchange_cn=data.exchange,
            name=data.name,
            page=data.page,
            extra=data.extra,
        )
    return build_page_quick_actions(data)


def _build_badge(data: AiContextData) -> str:
    if data.page == "选股":
        ctx = get_screening_results()
        if ctx is not None and ctx.count > 0:
            return f"选股·{ctx.count}"
        return "选股"
    if data.page in ("自选", "市场", "雷达", "本地", "数据管理"):
        return data.page[:2] if data.page == "数据管理" else data.page
    if data.page:
        return data.page[:2]
    return ""


def _build_chip_text(data: AiContextData) -> str:
    parts: list[str] = []
    if data.page:
        parts.append(data.page)
    if data.symbol and data.exchange:
        title = data.name or data.symbol
        parts.append(title)
        change = _extract_change_pct(data.quote_summary)
        if change:
            parts.append(change)
    elif data.page == "选股":
        ctx = get_screening_results()
        if ctx is not None and ctx.count > 0:
            parts.append(f"命中 {ctx.count} 条")
        else:
            parts.append("暂无结果")
    elif data.page == "数据管理" and data.extra:
        first_line = data.extra.splitlines()[1] if "\n" in data.extra else data.extra
        parts.append(first_line.replace("日线：", "").split("，")[0] if "日线" in first_line else "本地数据")
    return " · ".join(parts) if parts else "AI 助手"


def _extract_change_pct(quote_summary: str) -> str:
    if not quote_summary:
        return ""
    match = re.search(r"（([+-][\d.]+%)）", quote_summary)
    return match.group(1) if match else ""
