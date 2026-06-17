"""行情摘要格式化。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot


def format_quote_summary(quote: QuoteSnapshot | None) -> str:
    """将 QuoteSnapshot 格式化为单行行情摘要（AI 上下文用，字段较全）。"""
    if quote is None:
        return ""
    return (
        f"最新价 {quote.last_price:.2f}，涨跌 {quote.change_amount:+.2f}（{quote.change_pct:+.2f}%），"
        f"今开 {quote.open_price:.2f}，最高 {quote.high_price:.2f}，最低 {quote.low_price:.2f}，"
        f"昨收 {quote.prev_close:.2f}，换手率 {quote.turnover_rate:.2f}%"
    )


def format_quote_snapshot_line(quote: QuoteSnapshot) -> str:
    """简短现价摘要（笔记 / 日志附注）。"""
    if (quote.last_price or 0) <= 0:
        return ""
    return f"现价 {quote.last_price:.2f}，涨跌 {quote.change_pct:+.2f}%"
