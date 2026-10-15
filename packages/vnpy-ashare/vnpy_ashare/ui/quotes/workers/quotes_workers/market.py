"""市场页分页与全量榜单加载 Worker。"""

from __future__ import annotations

import logging

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_access import load_universe_page, load_universe_rows, load_universe_slice, search_universe
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.core.provider import get_redis_provider
from vnpy_ashare.quotes.rank.rank_catalog import get_rank_definition
from vnpy_ashare.quotes.rank.rank_engine import finalize_rank_catalog
from vnpy_ashare.quotes.rank.rank_scope import (
    build_stock_items_from_rank_symbols,
    load_market_rank_catalog,
    load_market_rank_catalog_from_eod,
    load_watchlist_rank_catalog,
    load_watchlist_tickflow_symbols,
    quotes_from_eod_snapshot,
)
from vnpy_ashare.ui.quotes.workers.quotes_workers.models import MarketFullResult, MarketPageResult

logger = logging.getLogger(__name__)


class MarketPageLoadWorker(QtCore.QThread):
    """市场页分页：Redis 涨幅榜或 universe 列表 + 行情。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        keyword: str,
        page: int,
        page_size: int,
        board: str | None = None,
        cached_total: int | None = None,
        rank_id: str = "change_pct",
    ) -> None:
        super().__init__()
        self.keyword = keyword.strip()
        self.page = max(page, 0)
        self.page_size = page_size
        self.board = board if board and board != "全部" else None
        self.cached_total = cached_total
        self.rank_id = rank_id
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            provider = get_redis_provider()
            offset = self.page * self.page_size
            updated_at: str | None = provider.updated_at()

            if self.keyword:
                rows, total = search_universe(
                    self.keyword,
                    limit=self.page_size,
                    offset=offset,
                    board=self.board,
                )
                if self._cancel_requested:
                    self.failed.emit("已取消")
                    return
                items = [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in rows]
                quotes = provider.get_quotes(items)
                mode = "search"
            elif self.board is None:
                items, quotes, total = provider.get_rank_page(
                    offset,
                    self.page_size,
                    rank_id=self.rank_id,
                )
                if self._cancel_requested:
                    self.failed.emit("已取消")
                    return
                mode = "rank"
            else:
                if self.cached_total is not None:
                    total = self.cached_total
                    rows = load_universe_slice(
                        offset=offset,
                        limit=self.page_size,
                        board=self.board,
                    )
                else:
                    rows, total = load_universe_page(
                        offset=offset,
                        limit=self.page_size,
                        board=self.board,
                    )
                if self._cancel_requested:
                    self.failed.emit("已取消")
                    return
                items = [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in rows]
                quotes = provider.get_quotes(items)
                mode = "list"

            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            source = "tushare" if getattr(provider, "using_eod_fallback", False) else "quote"
            if source == "tushare":
                updated_at = provider.updated_at() or updated_at
            self.finished.emit(
                MarketPageResult(
                    items=items,
                    quotes=quotes,
                    total=total,
                    page=self.page,
                    page_size=self.page_size,
                    mode=mode,
                    updated_at=updated_at,
                    board=self.board,
                    source=source,
                )
            )
        except Exception as ex:
            logger.exception(
                "市场页分页加载失败 rank_id=%s board=%s page=%s keyword=%r",
                self.rank_id,
                self.board,
                self.page,
                self.keyword,
            )
            self.failed.emit(str(ex))


class MarketFullLoadWorker(QtCore.QThread):
    """市场/榜单页全量：Redis 指定榜 + 全量行情（无榜时回退 universe）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, *, rank_id: str = "change_pct") -> None:
        super().__init__()
        self.rank_id = rank_id
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            provider = get_redis_provider()
            updated_at: str | None = provider.updated_at()
            store = provider._store
            spec = get_rank_definition(self.rank_id)
            name_map = {(symbol, exchange): name for symbol, exchange, name in load_universe_rows()}
            source = "quote"

            if spec.scope == "watchlist":
                tf_symbols, quotes = load_watchlist_rank_catalog(store, spec)
                if not any(quote.last_price > 0 for quote in quotes.values()):
                    eod_quotes, eod_updated_at = quotes_from_eod_snapshot()
                    if eod_quotes:
                        wl = load_watchlist_tickflow_symbols()
                        quotes = {tf: eod_quotes[tf] for tf in wl if tf in eod_quotes}
                        tf_symbols = finalize_rank_catalog(list(quotes.keys()), quotes, spec)
                        source = "tushare"
                        updated_at = eod_updated_at or updated_at
                if self._cancel_requested:
                    self.failed.emit("已取消")
                    return
                items = build_stock_items_from_rank_symbols(tf_symbols, quotes, name_map=name_map)
            else:
                tf_symbols, quotes = load_market_rank_catalog(
                    store,
                    spec,
                    universe_quotes_loader=lambda stock_items: store.get_quotes(
                        [item.tickflow_symbol for item in stock_items]
                    ),
                )
                if not tf_symbols or not any(quote.last_price > 0 for quote in quotes.values()):
                    tf_symbols, quotes, eod_updated_at = load_market_rank_catalog_from_eod(spec)
                    if tf_symbols:
                        source = "tushare"
                        updated_at = eod_updated_at or updated_at
                if self._cancel_requested:
                    self.failed.emit("已取消")
                    return
                items = build_stock_items_from_rank_symbols(tf_symbols, quotes, name_map=name_map)

            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(
                MarketFullResult(
                    items=items,
                    quotes=quotes,
                    updated_at=updated_at,
                    source=source,
                )
            )
        except Exception as ex:
            logger.exception("市场页全量榜单加载失败 rank_id=%s", self.rank_id)
            self.failed.emit(str(ex))
