"""从 Redis 加载全市场行情，供选股规则引擎使用。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_from_stock_and_snapshot
from vnpy_ashare.domain.symbols import StockItem, parse_tickflow_symbol
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot


class MarketQuotesLoadError(RuntimeError):
    """行情数据不可用。"""


class MarketQuotesSnapshot(FrozenModel):
    rows: list[QuoteRow] = Field(description="行情行列表")
    updated_at: str | None = Field(description="快照更新时间")
    total: int = Field(description="有效行情条数")
    source: str = Field(default="quote", description="数据来源标识")


def load_market_quote_rows(*, enrich_factors: bool = True) -> MarketQuotesSnapshot:
    """读取 Redis 全市场快照并转为 ScreeningService 可用行。"""
    store = RedisQuoteStore()
    tf_symbols = store.list_all_rank_symbols()
    if not tf_symbols:
        raise MarketQuotesLoadError("暂无全市场行情。请在「工具 → 立即执行 → 行情采集」运行后再选股。")

    quotes = store.get_quotes(tf_symbols, enrich_factors=enrich_factors)
    rows: list[QuoteRow] = []
    for tf_symbol in tf_symbols:
        quote = quotes.get(tf_symbol)
        if quote is None:
            continue
        item = parse_tickflow_symbol(tf_symbol, quote.name)
        if item is None:
            continue
        rows.append(quote_row_from_stock_and_snapshot(item, quote))

    if not rows:
        raise MarketQuotesLoadError("Redis 中无有效行情快照，请先运行行情采集。")

    return MarketQuotesSnapshot(
        rows=rows,
        updated_at=store.get_updated_at(),
        total=len(rows),
        source="quote",
    )


def row_from_item_quote(item: StockItem, quote: QuoteSnapshot) -> QuoteRow:
    """公开别名，供 data_source / 测试使用。"""
    return quote_row_from_stock_and_snapshot(item, quote)


def rows_as_dicts(rows: list[QuoteRow]) -> list[dict]:
    """过渡期：导出或 JSON 序列化。"""
    return [row.to_dict() for row in rows]
