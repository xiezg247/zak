"""行情上下文数据模型与组装。"""

from __future__ import annotations

from dataclasses import dataclass, field

from vnpy.trader.constant import Exchange

from vnpy_ashare.config import exchange_to_cn
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot


@dataclass
class QuickAction:
    """悬浮球/面板可点击的快捷动作。"""

    id: str
    label: str
    prompt: str
    auto_send: bool = False


@dataclass
class AiContextData:
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


def format_quote_summary(quote: QuoteSnapshot | None) -> str:
    if quote is None:
        return ""
    return (
        f"最新价 {quote.last_price:.2f}，涨跌 {quote.change_amount:+.2f}（{quote.change_pct:+.2f}%），"
        f"今开 {quote.open_price:.2f}，最高 {quote.high_price:.2f}，最低 {quote.low_price:.2f}，"
        f"昨收 {quote.prev_close:.2f}，换手率 {quote.turnover_rate:.2f}%"
    )


def build_quote_context(
    *,
    page: str,
    item: StockItem | None,
    quote: QuoteSnapshot | None = None,
    bar_count: int = 0,
) -> AiContextData:
    if item is None:
        return AiContextData(page=page)

    extra_parts: list[str] = []
    if bar_count > 0:
        extra_parts.append(f"本地日 K 条数：{bar_count}")
    else:
        extra_parts.append("本地日 K：暂无（需先下载）")

    return AiContextData(
        page=page,
        symbol=item.symbol,
        exchange=exchange_to_cn(item.exchange),
        name=item.name,
        quote_summary=format_quote_summary(quote),
        extra="\n".join(extra_parts),
    )


def build_diagnose_ai_prompt(vt_symbol: str, name: str = "") -> str:
    """生成跳转 AI 助手页的综合诊断预填文案。"""
    title = f"{name}（{vt_symbol}）" if name else vt_symbol
    return (
        f"请对 {title} 做综合诊断。"
        f'请调用 diagnose_stock(symbol="{vt_symbol}") 获取技术面与研报，'
        "基于工具返回结果解读，不要编造未在结果中的指标或研报观点。"
    )
