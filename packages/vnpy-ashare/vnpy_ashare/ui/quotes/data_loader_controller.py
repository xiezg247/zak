"""看盘页列表与市场榜数据加载。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from vnpy_ashare.data.bar_access import count_universe, universe_exists
from vnpy_ashare.app.engine_access import get_bar_service
from vnpy_ashare.ui.quotes.workers import (
    MarketFullLoadWorker,
    MarketFullResult,
    MarketPageLoadWorker,
    MarketPageResult,
    UniverseLoadWorker,
    UniverseSyncWorker,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.quotes_page import QuotesPage


class DataLoaderController:
    """QuotesPage 股票列表、市场榜分页与 A 股 universe 同步。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    @property
    def _p(self) -> QuotesPage:
        return self._page

    def refresh_market_clicked(self) -> None:
        page = self._p
        if page.market_auto_refresh_enabled():
            page._market_page = 0
            page._market_page_cache.clear()
            self.load_market_page(quiet=False)
            return
        if page.config.market_full_list:
            page._market_catalog_loaded = False
            self.load_market_full(quiet=False)
            return
        page._market_page = 0
        page._market_page_cache.clear()
        self.load_market_page(quiet=False)

    def try_load_more_market(self) -> None:
        page = self._p
        if not page.config.market_scroll_paging or page.config.market_full_list:
            return
        if not page._active or not page.config.use_market_rank:
            return
        if page._market_scroll_blocked or page._market_loading_more or page._thread_active(page._market_worker):
            return
        loaded = len(page.display_stocks)
        if page._market_total > 0 and loaded >= page._market_total:
            return

        from vnpy_ashare.ui.quotes.quotes_config import MARKET_SCROLL_LOAD_COOLDOWN_MS

        now = time.monotonic()
        if now - page._market_last_load_more_at < MARKET_SCROLL_LOAD_COOLDOWN_MS / 1000:
            return

        page._market_last_load_more_at = now
        page._market_loading_more = True
        page._market_page += 1
        page.status_label.setText(
            page._pagination.format_scroll_status(
                total=page._market_total,
                loaded=loaded,
                updated_at=page._market_updated_at,
                mode=page._market_load_mode,
                loading_more=True,
            )
        )
        self.load_market_page(quiet=True, append=True)

    def load_market_full(self, *, quiet: bool = False) -> None:
        page = self._p
        if not page._active or not page.config.use_market_rank or not page.config.market_full_list:
            return

        if not self._universe_exists():
            page.display_stocks = []
            page.quote_table_model.set_row_count(0)
            page._market_total = 0
            page.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        if page._thread_active(page._market_worker):
            return

        page._load_generation += 1
        generation = page._load_generation
        if not quiet:
            page._set_busy(True, lock_table=True)
            loading_text = (
                "正在加载全市场数据（排序）…"
                if page.market_auto_refresh_enabled()
                else "正在加载全市场数据…"
            )
            page._show_market_loading(loading_text)
            page.status_label.setText(loading_text)

        worker = MarketFullLoadWorker()
        page._market_worker = worker

        def on_finished(result: object) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            if generation != page._load_generation or not page._active:
                return
            if not isinstance(result, MarketFullResult):
                return

            page._market_catalog = list(result.items)
            page._market_catalog_quotes = dict(result.quotes)
            page._market_catalog_loaded = True
            page._market_updated_at = result.updated_at
            page.quote_map = dict(result.quotes)
            self.sync_market_quotes_to_cache_from_catalog()
            if not quiet:
                page._set_busy(False)
                page._hide_market_loading()
            page._table.filter_market_display()
            if page.market_auto_refresh_enabled():
                page._pagination.set_visible()
                page.schedule_quote_auto_refresh()
            else:
                page._pagination.set_visible(False)
                page._quote_timer.stop()
            page._pagination.update_controls()

        def on_failed(msg: str) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            if generation != page._load_generation or not page._active:
                return
            if not quiet:
                page._set_busy(False)
                page._hide_market_loading()
                page.status_label.setText(f"加载失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def load_market_page(self, *, quiet: bool = False, append: bool = False) -> None:
        page = self._p
        if not page._active or not page.config.use_market_rank:
            return
        if page.config.market_full_list and not page.market_auto_refresh_enabled():
            if page._market_catalog_loaded:
                page._table.filter_market_display()
            else:
                self.load_market_full(quiet=quiet)
            return

        if not self._universe_exists():
            page.display_stocks = []
            page.quote_table_model.set_row_count(0)
            page._market_total = 0
            page._pagination.update_controls()
            page.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        cache_key = self._market_page_cache_key()
        cached = page._market_page_cache.get(cache_key)
        if cached is not None:
            self._apply_market_page_result(cached, quiet=quiet, append=append)
            if append:
                page._market_loading_more = False
                self._prefetch_market_page(
                    page._market_page + 1,
                    generation=page._load_generation,
                )
            return

        if page._thread_active(page._market_worker):
            if append:
                page._market_loading_more = False
            return

        if not append:
            page._load_generation += 1
        generation = page._load_generation
        keyword = page.search_edit.text().strip()
        if quiet and not append:
            if page._thread_active(page._quotes_worker):
                return
        elif not append:
            page._set_busy(True, lock_table=False)
            page._show_market_loading("正在加载市场数据…")
            page.status_label.setText("正在加载市场数据...")

        cached_total = page._market_count_cache.get(page._market_board)
        worker = MarketPageLoadWorker(
            keyword=keyword,
            page=page._market_page,
            page_size=page.config.market_page_size,
            board=page._market_board,
            cached_total=cached_total,
        )
        page._market_worker = worker

        def on_finished(result: object) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            if generation != page._load_generation or not page._active:
                return
            if not isinstance(result, MarketPageResult):
                return

            page._market_page_cache[cache_key] = result
            page._market_count_cache[result.board] = result.total
            self._apply_market_page_result(result, quiet=quiet, append=append)
            if not append:
                self._prefetch_market_page(page._market_page + 1, generation=generation)
            else:
                page._market_loading_more = False
                self._prefetch_market_page(page._market_page + 1, generation=generation)

        def on_failed(msg: str) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            if generation != page._load_generation or not page._active:
                return
            if append:
                page._market_loading_more = False
                page._market_page = max(page._market_page - 1, 0)
                status = page._pagination.format_scroll_status(
                    total=page._market_total,
                    loaded=len(page.display_stocks),
                    updated_at=page._market_updated_at,
                    mode=page._market_load_mode,
                )
                page.status_label.setText(f"{status}（加载失败: {msg}）")
                return
            if not quiet:
                page._set_busy(False)
                page._hide_market_loading()
                page.status_label.setText(f"加载失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _market_page_cache_key(self) -> tuple[str | None, str, int]:
        page = self._p
        keyword = page.search_edit.text().strip()
        return (page._market_board, keyword, page._market_page)

    def _apply_market_page_result(
        self,
        result: MarketPageResult,
        *,
        quiet: bool,
        append: bool = False,
    ) -> None:
        page = self._p
        page._market_total = result.total
        page._market_updated_at = result.updated_at
        page._market_load_mode = result.mode

        if append:
            page._market_loading_more = False
            if not result.items:
                return
            start_row = len(page.display_stocks)
            page.display_stocks.extend(result.items)
            page.quote_map.update(result.quotes)
            page._table.append_rows(start_row, result.items, result.quotes)
        else:
            page.display_stocks = list(result.items)
            page.quote_map = dict(result.quotes)
            page._apply_default_table_sort = result.mode != "rank"
            page._render_table()

        if append:
            page._schedule_market_cache_sync()
        else:
            self.sync_market_quotes_to_cache_from_display()
        if not quiet and not append:
            page._set_busy(False)
            page._hide_market_loading()

        if page.config.market_scroll_paging:
            page.status_label.setText(
                page._pagination.format_scroll_status(
                    total=result.total,
                    loaded=len(page.display_stocks),
                    updated_at=result.updated_at,
                    mode=result.mode,
                    loading_more=page._market_loading_more,
                )
            )
        else:
            page._pagination.set_visible()
            page._pagination.update_controls()
            page.status_label.setText(page._pagination.format_status(result))
        page._update_quote_source_label()

        if page.market_auto_refresh_enabled():
            page.schedule_quote_auto_refresh()
        else:
            page._quote_timer.stop()

    def _prefetch_market_page(self, target_page: int, *, generation: int) -> None:
        page = self._p
        if page.config.market_full_list:
            return
        page_size = page.config.market_page_size
        if page._market_total <= 0 or page_size <= 0:
            return
        page_count = max((page._market_total + page_size - 1) // page_size, 1)
        if target_page < 0 or target_page >= page_count:
            return

        keyword = page.search_edit.text().strip()
        cache_key = (page._market_board, keyword, target_page)
        if cache_key in page._market_page_cache:
            return
        if page._thread_active(page._prefetch_worker):
            return

        cached_total = page._market_count_cache.get(page._market_board)
        if cached_total is None and page._market_board is not None:
            cached_total = count_universe(page._market_board)
            page._market_count_cache[page._market_board] = cached_total

        worker = MarketPageLoadWorker(
            keyword=keyword,
            page=target_page,
            page_size=page_size,
            board=page._market_board,
            cached_total=cached_total,
        )
        page._prefetch_worker = worker

        def on_finished(result: object) -> None:
            if page._prefetch_worker is worker:
                page._prefetch_worker = None
            if generation != page._load_generation or not page._active:
                return
            if not isinstance(result, MarketPageResult):
                return
            page._market_page_cache[cache_key] = result
            page._market_count_cache[result.board] = result.total

        def on_failed(_msg: str) -> None:
            if page._prefetch_worker is worker:
                page._prefetch_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def load_stock_list(self) -> None:
        page = self._p
        if not page._active:
            return

        if page.config.use_market_rank:
            page._market_page = 0
            page._pagination.set_visible()
            if page.market_auto_refresh_enabled():
                self.load_market_page()
                self.load_market_full(quiet=True)
            elif page.config.market_full_list:
                self.load_market_full()
            else:
                self.load_market_page()
            return

        page._load_generation += 1
        generation = page._load_generation
        scope_key = page.config.scope_key

        if scope_key == "全部A股" and not self._universe_exists():
            page.all_stocks = []
            page.display_stocks = []
            page.quote_table_model.set_row_count(0)
            page.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        page._set_busy(True, lock_table=True)
        loading_text = f"正在加载{page.page_name}…"
        page._show_market_loading(loading_text)
        page.status_label.setText(loading_text)
        page.quote_table_model.set_row_count(0)

        worker = UniverseLoadWorker(scope_key, local_scope=page._local_scope)
        page._load_worker = worker

        def on_finished(stocks: list) -> None:
            if page._load_worker is worker:
                page._load_worker = None
            if generation != page._load_generation or not page._active:
                return
            page.all_stocks = stocks
            page.apply_filter()
            page._set_busy(False)
            page._hide_market_loading()

        def on_failed(msg: str) -> None:
            if page._load_worker is worker:
                page._load_worker = None
            if generation != page._load_generation or not page._active:
                return
            page._set_busy(False)
            page._hide_market_loading()
            page.status_label.setText(f"加载失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def sync_universe_clicked(self) -> None:
        page = self._p
        if page._thread_active(page._sync_worker):
            return
        page._set_busy(True)
        page.status_label.setText("后台同步 A 股列表...")

        worker = UniverseSyncWorker()
        page._sync_worker = worker

        def on_finished(_path: str) -> None:
            if page._sync_worker is worker:
                page._sync_worker = None
            page._set_busy(False)
            page.status_label.setText("A 股列表同步完成")
            if page._active:
                page._market_catalog_loaded = False
                page._market_page_cache.clear()
                page._market_count_cache.clear()
                self.load_stock_list()

        def on_failed(msg: str) -> None:
            if page._sync_worker is worker:
                page._sync_worker = None
            page._set_busy(False)
            page.status_label.setText(f"同步失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def sync_market_quotes_to_cache(self, result: object) -> None:
        """将市场页行情写入 QuoteService 缓存，供 AI 选股工具使用。"""
        if not hasattr(result, "items") or not hasattr(result, "quotes"):
            return
        quote_svc = self._p._get_quote_service()
        if quote_svc is not None:
            quote_svc.set_market_quotes_cache(result.items, dict(result.quotes))

    def sync_market_quotes_to_cache_from_catalog(self) -> None:
        page = self._p
        quote_svc = page._get_quote_service()
        if quote_svc is not None and page._market_catalog:
            quote_svc.set_market_quotes_cache(page._market_catalog, page._market_catalog_quotes)

    def sync_market_quotes_to_cache_from_display(self) -> None:
        page = self._p
        quote_svc = page._get_quote_service()
        if quote_svc is not None and page.display_stocks:
            quote_svc.set_market_quotes_cache(page.display_stocks, page.quote_map)

    def flush_market_cache_sync(self) -> None:
        self.sync_market_quotes_to_cache_from_display()

    def _universe_exists(self) -> bool:
        """优先 BarService；无 Engine 时经 bar_access 探测本地 universe 表。"""
        bar_svc = get_bar_service(self._p._get_main_engine())
        if bar_svc is not None:
            return bar_svc.universe_exists()

        return universe_exists()
