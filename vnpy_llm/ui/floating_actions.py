"""悬浮球上下文增强：角标、Chip 文案、快捷动作（Phase 1 仅 badge/chip）。"""

from __future__ import annotations

import re
from dataclasses import replace

from vnpy_ashare.ai.context import (
    AiContextData,
    QuickAction,
    build_assistant_quick_actions,
    build_floating_stock_quick_actions,
    build_stock_quick_actions,
)
from vnpy_ashare.ai.session_context import get_screening_results


def enrich_context_with_actions(data: AiContextData) -> AiContextData:
    """为上下文填充 UI 用 badge、chip_text、actions。"""
    badge = _build_badge(data)
    chip_text = _build_chip_text(data)
    actions = _build_actions(data)
    return replace(data, badge=badge, chip_text=chip_text, actions=actions)


def _build_actions(data: AiContextData) -> list[QuickAction]:
    if data.page in ("自选", "市场", "本地") and data.symbol:
        return build_floating_stock_quick_actions(
            data.symbol,
            exchange_cn=data.exchange,
            name=data.name,
            page=data.page,
            extra=data.extra,
        )
    return _build_page_actions(data)


def _build_page_actions(data: AiContextData) -> list[QuickAction]:
    if data.page == "选股":
        ctx = get_screening_results()
        if ctx is not None and ctx.count > 0:
            return [
                QuickAction(
                    id="interpret_screen",
                    label="解读选股结果",
                    prompt=(
                        f"请解读选股结果「{ctx.condition}」（共 {ctx.count} 条）。"
                        "请调用 get_screening_context 获取数据后解读前几只标的。"
                    ),
                ),
            ]
    if data.page == "数据管理":
        return [
            QuickAction(
                id="data_gap",
                label="检查数据缺口",
                prompt=(
                    "请根据当前本地 K 线覆盖情况，分析可能存在的数据缺口，"
                    "并说明建议优先补全哪些标的或周期。可结合 get_bars_summary 等工具。"
                ),
            ),
        ]
    return []


def _build_badge(data: AiContextData) -> str:
    if data.page == "选股":
        ctx = get_screening_results()
        if ctx is not None and ctx.count > 0:
            return f"选股·{ctx.count}"
        return "选股"
    if data.page in ("自选", "市场", "本地", "数据管理"):
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


def build_quick_actions_for_panel(data: AiContextData, *, mode: str) -> list[QuickAction]:
    """按面板模式组装快捷按钮（floating / compact / assistant）。"""
    if mode == "assistant":
        return build_assistant_quick_actions()
    if data.page in ("自选", "市场", "本地") and data.symbol:
        return build_floating_stock_quick_actions(
            data.symbol,
            exchange_cn=data.exchange,
            name=data.name,
            page=data.page,
            extra=data.extra,
        )
    return _build_page_actions(data)


def scene_label_from_context(data: AiContextData) -> str:
    """从 AI 上下文生成会话场景标签。"""
    if data.badge and data.symbol and data.name:
        return f"{data.badge} · {data.name}"
    if data.badge and data.page == "选股":
        return data.badge
    if data.chip_text and data.chip_text != "AI 助手":
        return data.chip_text
    return data.page or data.badge


def orb_tooltip_text(data: AiContextData) -> str:
    lines = ["AI 助手 · 左键对话 · 右键菜单 · Ctrl+L 显示/隐藏"]
    if data.chip_text and data.chip_text != "AI 助手":
        lines.append(data.chip_text)
    text = data.to_text()
    if text:
        lines.append(text)
    return "\n".join(lines)
