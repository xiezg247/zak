"""行情 Provider：市场只读 Redis，自选 TickFlow 直连。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.integrations.tickflow.quotes import fetch_quotes_from_tickflow
from vnpy_ashare.quotes.core.enrich import fill_missing_tushare_factors
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.core.screening_snapshot_router import load_screening_quote_snapshot
from vnpy_ashare.quotes.rank.rank_catalog import get_rank_definition
from vnpy_ashare.quotes.rank.rank_scope import (
    build_stock_items_from_rank_symbols,
    load_market_rank_catalog,
    load_watchlist_rank_catalog,
    paginate_symbols,
)

QuoteSource = Literal["market", "watchlist"]


class QuoteProviderError(Exception):
    """行情 Provider 不可用。"""


class QuoteProvider(ABC):
    @abstractmethod
    def get_quotes(self, items: list[StockItem]) -> dict[str, QuoteSnapshot]:
        raise NotImplementedError

    def get_rank_page(
        self,
        offset: int,
        limit: int,
    ) -> tuple[list[StockItem], dict[str, QuoteSnapshot], int]:
        raise NotImplementedError("当前 Provider 不支持涨幅榜分页")


class TickflowQuoteProvider(QuoteProvider):
    def get_quotes(self, items: list[StockItem]) -> dict[str, QuoteSnapshot]:
        quotes = fetch_quotes_from_tickflow(items)
        fill_missing_tushare_factors(quotes)
        return quotes


class RedisQuoteProvider(QuoteProvider):
    def __init__(self, store: RedisQuoteStore | None = None) -> None:
        self._store = store or RedisQuoteStore()

    def get_quotes(self, items: list[StockItem]) -> dict[str, QuoteSnapshot]:
        tf_symbols = [item.tickflow_symbol for item in items]
        return self._store.get_quotes(tf_symbols)

    def get_rank_page(
        self,
        offset: int,
        limit: int,
        *,
        rank_id: str = "change_pct",
    ) -> tuple[list[StockItem], dict[str, QuoteSnapshot], int]:
        spec = get_rank_definition(rank_id)
        if spec.scope == "watchlist":
            tf_symbols, quotes = load_watchlist_rank_catalog(self._store, spec)
            total = len(tf_symbols)
            page_symbols = paginate_symbols(tf_symbols, offset, limit)
            page_quotes = {symbol: quotes[symbol] for symbol in page_symbols if symbol in quotes}
            items = build_stock_items_from_rank_symbols(page_symbols, page_quotes)
            return items, page_quotes, total

        tf_symbols, quotes = load_market_rank_catalog(
            self._store,
            spec,
            universe_quotes_loader=self.get_quotes,
        )
        total = len(tf_symbols)
        page_symbols = paginate_symbols(tf_symbols, offset, limit)
        page_quotes = {symbol: quotes[symbol] for symbol in page_symbols if symbol in quotes}

        items = build_stock_items_from_rank_symbols(page_symbols, page_quotes)
        return items, page_quotes, total

    def updated_at(self) -> str | None:
        return self._store.get_updated_at()


_tickflow_provider: TickflowQuoteProvider | None = None
_redis_provider: RedisQuoteProvider | None = None


def get_tickflow_provider() -> TickflowQuoteProvider:
    global _tickflow_provider
    if _tickflow_provider is None:
        _tickflow_provider = TickflowQuoteProvider()
    return _tickflow_provider


def get_redis_provider() -> RedisQuoteProvider:
    global _redis_provider
    if _redis_provider is None:
        store = RedisQuoteStore()
        try:
            store.ping()
        except Exception as ex:
            raise QuoteProviderError("Redis 不可用，市场页无法加载行情") from ex
        _redis_provider = RedisQuoteProvider(store)
    return _redis_provider


def reset_quote_providers() -> None:
    """配置热重载后丢弃 Provider 单例，下次访问重建。"""
    global _tickflow_provider, _redis_provider
    _tickflow_provider = None
    _redis_provider = None


def get_quote_provider(source: QuoteSource) -> QuoteProvider:
    if source == "market":
        return get_redis_provider()
    return get_tickflow_provider()


def fetch_quotes(items: list[StockItem], source: QuoteSource) -> dict[str, QuoteSnapshot]:
    return get_quote_provider(source).get_quotes(items)


def _optional_float(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = row.get(key)
        if isinstance(raw, (int, float)):
            return float(raw)
    return None


def quote_snapshot_from_row(row: dict[str, Any], *, tickflow_symbol: str = "") -> QuoteSnapshot | None:
    """从 screening / 行情行构造 QuoteSnapshot（字段可不全）。"""
    last_price = _optional_float(row, "last_price", "close")
    if last_price is None or last_price <= 0:
        return None
    symbol = str(row.get("symbol") or "").strip()
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    item = parse_stock_symbol(vt_symbol) if vt_symbol else None
    tf_symbol = tickflow_symbol or (item.tickflow_symbol if item else "")
    if not symbol and item is not None:
        symbol = item.symbol
    if not tf_symbol and symbol:
        parsed = parse_stock_symbol(symbol)
        tf_symbol = parsed.tickflow_symbol if parsed else symbol

    change_pct = _optional_float(row, "change_pct", "pct_chg") or 0.0
    prev_close = _optional_float(row, "prev_close")
    if (prev_close is None or prev_close <= 0) and change_pct != 0:
        prev_close = last_price / (1 + change_pct / 100.0)
    change_amount = _optional_float(row, "change_amount")
    if (change_amount is None or change_amount == 0) and prev_close is not None and prev_close > 0:
        change_amount = last_price - prev_close

    return QuoteSnapshot(
        symbol=tf_symbol or symbol,
        name=str(row.get("name") or (item.name if item else "") or ""),
        last_price=last_price,
        prev_close=prev_close or 0.0,
        open_price=_optional_float(row, "open_price", "open") or 0.0,
        high_price=_optional_float(row, "high_price", "high") or 0.0,
        low_price=_optional_float(row, "low_price", "low") or 0.0,
        change_amount=change_amount or 0.0,
        change_pct=change_pct,
        turnover_rate=_optional_float(row, "turnover_rate") or 0.0,
        volume=_optional_float(row, "volume") or 0.0,
        amount=_optional_float(row, "amount") or 0.0,
        amplitude=_optional_float(row, "amplitude") or 0.0,
        volume_ratio=_optional_float(row, "volume_ratio") or 0.0,
        net_mf_amount=_optional_float(row, "net_mf_amount") or 0.0,
        change_speed_5m=_optional_float(row, "change_speed_5m") or 0.0,
        limit_times=_optional_float(row, "limit_times") or 0.0,
        trade_time=str(row.get("trade_time") or row.get("trade_date") or row.get("updated_at") or ""),
    )


def resolve_quote_snapshot(
    item: StockItem,
    *,
    quote_map: dict[str, QuoteSnapshot] | None = None,
    row_hint: dict[str, Any] | None = None,
) -> QuoteSnapshot | None:
    """解析单标的行情：宿主 map → 行 hint → Redis → 全市场快照 → TickFlow。"""
    tf_symbol = item.tickflow_symbol

    if quote_map:
        quote = quote_map.get(tf_symbol)
        if quote is not None and quote.last_price > 0:
            return quote

    if row_hint is not None:
        quote = quote_snapshot_from_row(row_hint, tickflow_symbol=tf_symbol)
        if quote is not None:
            if not quote.name and item.name:
                quote = QuoteSnapshot(
                    symbol=quote.symbol,
                    name=item.name,
                    last_price=quote.last_price,
                    prev_close=quote.prev_close,
                    open_price=quote.open_price,
                    high_price=quote.high_price,
                    low_price=quote.low_price,
                    change_amount=quote.change_amount,
                    change_pct=quote.change_pct,
                    turnover_rate=quote.turnover_rate,
                    volume=quote.volume,
                    amount=quote.amount,
                    amplitude=quote.amplitude,
                    trade_time=quote.trade_time,
                )
            return quote

    try:
        quotes = RedisQuoteStore().get_quotes([tf_symbol])
        quote = quotes.get(tf_symbol)
        if quote is not None and quote.last_price > 0:
            return quote
    except Exception:
        pass

    try:
        for row in get_market_quotes_cache():
            vt = str(row.get("vt_symbol") or "").strip()
            sym = str(row.get("symbol") or "").strip()
            if vt == item.vt_symbol or sym == item.symbol:
                quote = quote_snapshot_from_row(row.to_dict(), tickflow_symbol=tf_symbol)
                if quote is not None:
                    return quote
    except Exception:
        pass

    try:
        snapshot = load_screening_quote_snapshot()
        for row in snapshot.rows:
            vt = str(row.get("vt_symbol") or "").strip()
            sym = str(row.get("symbol") or "").strip()
            if vt == item.vt_symbol or sym == item.symbol:
                quote = quote_snapshot_from_row(row.to_dict(), tickflow_symbol=tf_symbol)
                if quote is not None:
                    if not quote.trade_time and snapshot.updated_at:
                        quote = QuoteSnapshot(
                            symbol=quote.symbol,
                            name=quote.name or item.name,
                            last_price=quote.last_price,
                            prev_close=quote.prev_close,
                            open_price=quote.open_price,
                            high_price=quote.high_price,
                            low_price=quote.low_price,
                            change_amount=quote.change_amount,
                            change_pct=quote.change_pct,
                            turnover_rate=quote.turnover_rate,
                            volume=quote.volume,
                            amount=quote.amount,
                            amplitude=quote.amplitude,
                            trade_time=str(snapshot.updated_at or ""),
                        )
                    return quote
    except Exception:
        pass

    try:
        quotes = fetch_quotes_from_tickflow([item])
        quote = quotes.get(tf_symbol)
        if quote is not None and quote.last_price > 0:
            return quote
    except Exception:
        return None
    return None


def is_gateway_quote_active() -> bool:
    """P4：Gateway 已连接且为行情主源时返回 True。"""
    return False
