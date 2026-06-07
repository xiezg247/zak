"""AI 上下文事件。"""

from __future__ import annotations

from dataclasses import dataclass

EVENT_AI_CONTEXT = "eAiContext"


@dataclass
class AiContextData:
    page: str = ""
    symbol: str = ""
    exchange: str = ""
    name: str = ""
    quote_summary: str = ""
    extra: str = ""

    def to_text(self) -> str:
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
