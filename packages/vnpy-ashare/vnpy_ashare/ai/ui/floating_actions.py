"""悬浮球 UI 展示：面板快捷按钮组装、场景标签与 tooltip。"""

from __future__ import annotations

from vnpy_ashare.ai.context.enrichment import (
    build_assistant_panel_quick_actions,
    build_context_quick_actions,
)
from vnpy_common.ai.protocol import AiContextData, QuickAction


def build_quick_actions_for_panel(data: AiContextData, *, mode: str) -> list[QuickAction]:
    """按面板模式组装快捷按钮（floating / compact / assistant）。"""
    if mode == "assistant":
        return build_assistant_panel_quick_actions()
    return build_context_quick_actions(data)


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
