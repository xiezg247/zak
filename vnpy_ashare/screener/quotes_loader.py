"""从 Redis 加载全市场行情，供选股规则引擎使用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_ashare.models import StockItem, parse_tickflow_symbol
from vnpy_ashare.quotes.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.snapshot import QuoteSnapshot


class MarketQuotesLoadError(RuntimeError):
    """行情数据不可用。"""


@dataclass(frozen=True)
class MarketQuotesSnapshot:
    rows: list[dict[str, Any]]
    updated_at: str | None
    total: int
    source: str = "quote"


def load_market_quote_rows() -> MarketQuotesSnapshot:
    """读取 Redis 全市场快照并转为 ScreeningService 可用行。"""
    store = RedisQuoteStore()
    tf_symbols = store.list_all_rank_symbols()
    if not tf_symbols:
        raise MarketQuotesLoadError("暂无全市场行情。请在「工具 → 立即执行 → 行情采集」运行后再选股。")

    quotes = store.get_quotes(tf_symbols)
    rows: list[dict[str, Any]] = []
    for tf_symbol in tf_symbols:
        quote = quotes.get(tf_symbol)
        if quote is None:
            continue
        item = parse_tickflow_symbol(tf_symbol, quote.name)
        if item is None:
            continue
        rows.append(_row_from_item_quote(item, quote))

    if not rows:
        raise MarketQuotesLoadError("Redis 中无有效行情快照，请先运行行情采集。")

    return MarketQuotesSnapshot(
        rows=rows,
        updated_at=store.get_updated_at(),
        total=len(rows),
        source="quote",
    )


def _row_from_item_quote(item: StockItem, quote: QuoteSnapshot) -> dict[str, Any]:
    return {
        "symbol": item.symbol,
        "name": quote.name or item.name,
        "vt_symbol": item.vt_symbol,
        "exchange": item.exchange.value,
        "last_price": quote.last_price,
        "change_pct": quote.change_pct,
        "turnover_rate": quote.turnover_rate,
        "volume": quote.volume,
    }
