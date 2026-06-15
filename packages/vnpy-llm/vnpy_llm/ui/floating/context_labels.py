"""仅依赖 AiContextData 协议的 UI 文案工具。"""

from __future__ import annotations

from vnpy_common.ai.protocol import AiContextData


def _text(value: object) -> str:
    return str(value or "")


def scene_label_from_context(data: AiContextData) -> str:
    """从 AI 上下文生成会话场景标签。"""
    if data.badge and data.symbol and data.name:
        return f"{data.badge} · {data.name}"
    if data.badge and data.page == "选股":
        return _text(data.badge)
    if data.chip_text and data.chip_text != "AI 助手":
        return _text(data.chip_text)
    return _text(data.page or data.badge)


def orb_tooltip_text(data: AiContextData) -> str:
    lines = ["AI 助手 · 左键对话 · 右键菜单 · Ctrl+L 显示/隐藏"]
    if data.chip_text and data.chip_text != "AI 助手":
        lines.append(data.chip_text)
    text = data.to_text()
    if text:
        lines.append(text)
    return "\n".join(lines)
