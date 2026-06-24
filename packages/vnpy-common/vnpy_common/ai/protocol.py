"""AI 助手上下文协议（纯数据模型，无业务依赖）。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel, MutableModel


class QuickAction(MutableModel):
    """悬浮球/面板可点击的快捷动作；`children` 非空时展示二级菜单。"""

    id: str = Field(description="动作标识")
    label: str = Field(description="展示标签")
    prompt: str = Field(default="", description="点击后填入的提示词")
    auto_send: bool = Field(default=False, description="是否自动发送")
    tooltip: str = Field(default="", description="悬停提示")
    children: list[QuickAction] = Field(default_factory=list, description="二级菜单项")

    @property
    def has_menu(self) -> bool:
        return bool(self.children)


class AiContextData(MutableModel):
    """AI 助手当前会话上下文（页面、选中标的、摘要与快捷动作）。"""

    page: str = Field(default="", description="当前页面")
    symbol: str = Field(default="", description="证券代码")
    exchange: str = Field(default="", description="交易所")
    name: str = Field(default="", description="证券名称")
    quote_summary: str = Field(default="", description="行情摘要")
    extra: str = Field(default="", description="附加说明")
    badge: str = Field(default="", description="悬浮球角标")
    chip_text: str = Field(default="", description="上下文芯片文案")
    actions: list[QuickAction] = Field(default_factory=list, description="快捷动作列表")

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


class StockCompletionItem(FrozenModel):
    """输入联想项：短标签 + 完整 prompt。"""

    label: str = Field(description="展示标签")
    prompt: str = Field(description="完整提示词")


class SymbolRef(FrozenModel):
    """跨包传递的标的引用（供 LLM 助手跳转 ashare UI）。"""

    symbol: str = Field(description="证券代码")
    exchange: str = Field(description="交易所枚举名，如 SSE")
    name: str = Field(default="", description="证券名称")
    vt_symbol: str = Field(description="VeighNa 合约代码")


class WatchlistToggleResult(FrozenModel):
    """自选 toggle 操作结果（供 UI notify）。"""

    level: str = Field(description="success / info / warning / error")
    message: str = Field(description="用户可见文案")


class AiChartBar(FrozenModel):
    """迷你图单根 K 线 / 折线点。"""

    date: str = Field(description="日期 YYYY-MM-DD")
    open: float = Field(description="开盘价")
    high: float = Field(description="最高价")
    low: float = Field(description="最低价")
    close: float = Field(description="收盘价")
    volume: int = Field(default=0, description="成交量")


class AiChartSpec(FrozenModel):
    """AI 聊天内嵌迷你图规格（由工具结果生成，非 LLM 编造）。"""

    chart_id: str = Field(description="图表唯一 ID")
    kind: Literal["line", "candlestick"] = Field(description="图表类型")
    symbol: str = Field(description="vt_symbol，如 600519.SSE")
    chart_key: str = Field(default="", description="去重键，默认等同 symbol")
    name: str = Field(default="", description="证券名称")
    scope: str = Field(default="daily", description="K 线周期")
    caption: str = Field(default="", description="图表标题/说明")
    series: list[AiChartBar] = Field(default_factory=list, description="OHLCV 序列")
    overlays: list[dict[str, object]] = Field(default_factory=list, description="叠加层（Phase 2）")
    source_tool: str = Field(default="", description="来源工具名")
