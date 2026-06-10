"""AI 助手上下文协议（纯数据模型，无业务依赖）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QuickAction:
    """悬浮球/面板可点击的快捷动作；`children` 非空时展示二级菜单。"""

    id: str
    label: str
    prompt: str = ""
    auto_send: bool = False
    tooltip: str = ""
    children: list[QuickAction] = field(default_factory=list)

    @property
    def has_menu(self) -> bool:
        return bool(self.children)


@dataclass
class AiContextData:
    """AI 助手当前会话上下文（页面、选中标的、摘要与快捷动作）。"""

    page: str = ""
    symbol: str = ""
    exchange: str = ""
    name: str = ""
    quote_summary: str = ""
    extra: str = ""
    badge: str = ""
    chip_text: str = ""
    actions: list[QuickAction] = field(default_factory=list)

    def to_text(self) -> str:
        """序列化为 System Prompt 可读的多行文本。"""
        lines: list[str] = []
        if self.page:
            lines.append(f"当前页面：{self.page}")
        if self.symbol and self.exchange:
            title = self.name or self.symbol
            lines.append(f"当前选中：{title}（{self.symbol}.{self.exchange}）")
        if self.quote_summary:
            lines.append(f"行情摘要：{self.quote_summary}")
        if self.extra:
            lines.append(self.extra)
        return "\n".join(lines)


@dataclass(frozen=True)
class StockCompletionItem:
    """输入联想项：短标签 + 完整 prompt。"""

    label: str
    prompt: str
