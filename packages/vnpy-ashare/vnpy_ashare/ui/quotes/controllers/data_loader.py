"""看盘页列表与市场榜数据加载。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from vnpy_ashare.app.engine_access import get_bar_service
from vnpy_ashare.data.bar_access import count_universe, universe_exists
from vnpy_ashare.quotes.core.enrich import merge_quote_maps_into
from vnpy_ashare.ui.quotes.page.config import MARKET_SCROLL_LOAD_COOLDOWN_MS
from vnpy_ashare.ui.quotes.workers import (
    MarketFullLoadWorker,
    MarketFullResult,
    MarketPageLoadWorker,
    MarketPageResult,
    UniverseLoadResult,
    UniverseLoadWorker,
    UniverseSyncWorker,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class DataLoaderController:
    """QuotesPage 股票列表、市场榜分页与 A 股 universe 同步。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    @property
    def _p(self) -> QuotesPage:
        return self._page

    def _begin_loader_task(
        self,
        message: str,
        *,
        worker_attr: str,
        primary=None,
        primary_text: str = "",
        primary_handler=None,
        lock_table: bool = True,
    ) -> bool:
        page = self._p
        if page._task_guard.active:
            return False
        page._begin_cancellable_task(
            message,
            worker_attr=worker_attr,
            primary=primary,
            primary_text=primary_text,
            primary_handler=primary_handler,
            lock_table=lock_table,
        )
        return True

    def refresh_market_clicked(self) -> None:
        page = self._p
        if page.market_auto_refresh_enabled():
            page._market_page = 0
            page._market_page_cache.clear()
            self.load_market_page(quiet=False)
            return
        if page.config.market_full_list:
            page._market_catalog_loaded = False
            page._market_page = 0
            page._market_page_cache.clear()
            page._market_full_load_quiet = False
            self.load_market_page(quiet=False)
            return
        page._market_page = 0
        page._market_page_cache.clear()
        self.load_market_page(quiet=False)

    def _schedule_market_catalog_load(self, *, quiet: bool | None = None) -> None:
        """首屏分页展示后，后台拉全量 catalog 以支持客户端排序与翻页。"""
        page = self._p
        if not page.config.market_full_list or page._market_catalog_loaded:
            return
        if quiet is not None:
            page._market_full_load_quiet = quiet
        if page._thread_active(page._market_worker):
            return
        self.load_market_full(quiet=page._market_full_load_quiet)

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

        page._wait_worker_release("_market_worker", timeout_ms=0)
        page._load_generation += 1
        generation = page._load_generation
        loading_text = "正在加载全市场数据（排序）…" if page.market_auto_refresh_enabled() else "正在加载全市场数据…"
        if not quiet:
            if not self._begin_loader_task(
                loading_text,
                worker_attr="_market_worker",
                primary=page.refresh_quotes_button,
                primary_text="刷新行情",
                primary_handler=page._refresh_market_clicked,
                lock_table=True,
            ):
                return
            page._show_market_loading(loading_text)
            page.status_label.setText(loading_text)

        worker = MarketFullLoadWorker(rank_id=page._market_rank_id)
        page._market_worker = worker

        def on_finished(result: object) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            try:
                if generation != page._load_generation or not page._active:
                    return
                if not isinstance(result, MarketFullResult):
                    return

                page._market_catalog = list(result.items)
                page._market_catalog_quotes = dict(result.quotes)
                page._market_board_base = None
                page._market_board_base_key = None
                page._market_filter_keyword = ""
                pending_industry = page._pending_industry_drilldown
                pending_concept = page._pending_concept_drilldown
                page._pending_industry_drilldown = None
                page._pending_concept_drilldown = None
                if pending_concept:
                    page._market_vt_whitelist = pending_concept
                    page._market_industry_filter = None
                    listener = page._market_industry_filter_listener
                    if listener is not None:
                        listener(None)
                elif pending_industry:
                    page._market_vt_whitelist = None
                    page._market_drilldown_label = None
                    page._market_industry_filter = pending_industry
                    listener = page._market_industry_filter_listener
                    if listener is not None:
                        listener(pending_industry)
                else:
                    page._market_industry_filter = None
                    page._market_vt_whitelist = None
                    page._market_drilldown_label = None
                    listener = page._market_industry_filter_listener
                    if listener is not None:
                        listener(None)
                page._industry_map_cache = None
                page._market_board_map_cache = None
                page._market_catalog_loaded = True
                page._market_updated_at = result.updated_at
                page.quote_map = dict(result.quotes)
                self.sync_market_quotes_to_cache_from_catalog()
                self._sync_market_overview_breadth(page)
                if not quiet:
                    if page._finish_cancellable_task(cancelled_message="加载已取消"):
                        page._hide_market_loading()
                        return
                    page._hide_market_loading()
                page._table.filter_market_display()
                page._pagination.set_visible()
                if page.market_auto_refresh_enabled():
                    page.schedule_quote_auto_refresh()
                else:
                    page._quote_timer.stop()
                page._pagination.update_controls()
            finally:
                page._release_worker(worker)

        def on_failed(msg: str) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            try:
                if generation != page._load_generation or not page._active:
                    return
                if not quiet:
                    if page._finish_cancellable_task(cancelled_message="加载已取消"):
                        page._hide_market_loading()
                        return
                    page._hide_market_loading()
                    page.status_label.setText(f"加载失败: {msg}")
                    page._toast.error(msg)
            finally:
                page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def load_market_page(self, *, quiet: bool = False, append: bool = False) -> None:
        page = self._p
        if not page._active or not page.config.use_market_rank:
            return
        if page.market_uses_client_pagination():
            page._table.filter_market_display()
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
            page._wait_worker_release("_market_worker", timeout_ms=0)
            page._load_generation += 1
        generation = page._load_generation
        keyword = page.search_edit.text().strip()
        if quiet and not append:
            if page._thread_active(page._quotes_worker):
                return
        elif not append:
            if not self._begin_loader_task(
                "正在加载市场数据…",
                worker_attr="_market_worker",
                primary=page.refresh_quotes_button,
                primary_text="刷新行情",
                primary_handler=page._refresh_market_clicked,
                lock_table=False,
            ):
                return
            page._show_market_loading("正在加载市场数据…")
            page.status_label.setText("正在加载市场数据...")

        cached_total = page._market_count_cache.get(page._market_board)
        worker = MarketPageLoadWorker(
            keyword=keyword,
            page=page._market_page,
            page_size=page.config.market_page_size,
            board=page._market_board,
            cached_total=cached_total,
            rank_id=page._market_rank_id,
        )
        page._market_worker = worker

        def on_finished(result: object) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            try:
                if generation != page._load_generation or not page._active:
                    return
                if not isinstance(result, MarketPageResult):
                    return

                page._market_page_cache[cache_key] = result
                page._market_count_cache[result.board] = result.total
                self._apply_market_page_result(result, quiet=quiet, append=append)
                if not append:
                    self._schedule_market_catalog_load()
                    self._prefetch_market_page(page._market_page + 1, generation=generation)
                else:
                    page._market_loading_more = False
                    self._prefetch_market_page(page._market_page + 1, generation=generation)
            finally:
                page._release_worker(worker)

        def on_failed(msg: str) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            try:
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
                if not quiet and not append:
                    if page._finish_cancellable_task(cancelled_message="加载已取消"):
                        page._hide_market_loading()
                        return
                    page._hide_market_loading()
                    page.status_label.setText(f"加载失败: {msg}")
                    page._toast.error(msg)
            finally:
                page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _market_page_cache_key(self) -> tuple[str, str | None, str, int]:
        page = self._p
        keyword = page.search_edit.text().strip()
        return (page._market_rank_id, page._market_board, keyword, page._market_page)

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

            merge_quote_maps_into(page.quote_map, result.quotes)
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
            if page._finish_cancellable_task(cancelled_message="加载已取消"):
                page._hide_market_loading()
                return
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
            status = page._pagination.format_status(result)
            if page.config.market_full_list and not page._market_catalog_loaded:
                status += "；正在同步全市场排序…"
            page.status_label.setText(status)
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
        cache_key = (page._market_rank_id, page._market_board, keyword, target_page)
        if cache_key in page._market_page_cache:
            return
        if page._thread_active(page._prefetch_worker):
            return
        page._wait_worker_release("_prefetch_worker", timeout_ms=0)

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
            rank_id=page._market_rank_id,
        )
        page._prefetch_worker = worker

        def on_finished(result: object) -> None:
            if page._prefetch_worker is worker:
                page._prefetch_worker = None
            try:
                if generation != page._load_generation or not page._active:
                    return
                if not isinstance(result, MarketPageResult):
                    return
                page._market_page_cache[cache_key] = result
                page._market_count_cache[result.board] = result.total
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._prefetch_worker is worker:
                page._prefetch_worker = None
            page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def load_stock_list(self) -> None:
        page = self._p
        if not page._active:
            return

        if page.config.use_market_rank:
            page._market_page = 0
            page._pagination.set_visible()
            if page.config.market_full_list:
                page._market_full_load_quiet = True
            self.load_market_page()
            return

        page._wait_worker_release("_load_worker", timeout_ms=0)
        page._load_generation += 1
        generation = page._load_generation
        scope_key = page.config.scope_key

        if scope_key == "全部A股" and not self._universe_exists():
            page.all_stocks = []
            page.display_stocks = []
            page.quote_table_model.set_row_count(0)
            page.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        loading_text = f"正在加载{page.page_name}…"
        if not self._begin_loader_task(
            loading_text,
            worker_attr="_load_worker",
            lock_table=True,
        ):
            return
        page._show_market_loading(loading_text)
        page.status_label.setText(loading_text)
        page.quote_table_model.set_row_count(0)

        if page.config.use_local_pagination and scope_key == "已下载":
            offset = page._market_page * page.config.local_page_size
            limit = page.config.local_page_size
            keyword = page.search_edit.text().strip()
        else:
            offset = 0
            limit = None
            keyword = ""

        worker = UniverseLoadWorker(
            scope_key,
            local_scope=page._local_scope,
            offset=offset,
            limit=limit,
            keyword=keyword,
        )
        page._load_worker = worker

        def on_finished(result: object) -> None:
            if page._load_worker is worker:
                page._load_worker = None
            try:
                if generation != page._load_generation or not page._active:
                    return
                if isinstance(result, UniverseLoadResult):
                    page.all_stocks = list(result.items)
                    page._local_total = result.total
                elif isinstance(result, list):
                    page.all_stocks = result
                    page._local_total = len(result)
                else:
                    return
                if page._finish_cancellable_task(cancelled_message="加载已取消"):
                    page._hide_market_loading()
                    return
                page._hide_market_loading()
                if page.config.use_local_pagination:
                    page._pagination.set_visible()
                    page._pagination.update_controls()
                if page.config.use_local_table:
                    page._local.on_stock_list_loaded()
                elif page._watchlist_groups is not None:
                    page._watchlist_groups.on_stock_list_loaded(list(page.all_stocks))
                    page._watchlist.refresh_keys()
                    if page.config.show_watchlist_signals:
                        page._signals.on_stock_list_loaded()
                    if page.config.show_watchlist_positions:
                        page._positions.on_stock_list_loaded()
                else:
                    page.apply_filter()
                    if page.page_name == "自选":
                        page._watchlist.refresh_keys()
                    if page.config.show_watchlist_signals:
                        page._signals.on_stock_list_loaded()
                    if page.config.show_watchlist_positions:
                        page._positions.on_stock_list_loaded()
                    if page.config.show_watchlist_multiview:
                        page._multiview.on_stock_list_loaded()
            finally:
                page._release_worker(worker)

        def on_failed(msg: str) -> None:
            if page._load_worker is worker:
                page._load_worker = None
            try:
                if generation != page._load_generation or not page._active:
                    return
                if page._finish_cancellable_task(cancelled_message="加载已取消"):
                    page._hide_market_loading()
                    return
                page._hide_market_loading()
                page.status_label.setText(f"加载失败: {msg}")
                page._toast.error(msg)
            finally:
                page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def sync_universe_clicked(self) -> None:
        page = self._p
        if page._thread_active(page._sync_worker):
            return
        page._wait_worker_release("_sync_worker", timeout_ms=0)
        if not self._begin_loader_task(
            "后台同步 A 股列表…",
            worker_attr="_sync_worker",
            primary=page.sync_button,
            primary_text="同步 A 股列表",
            primary_handler=page.sync_universe_clicked,
            lock_table=False,
        ):
            return
        page.status_label.setText("后台同步 A 股列表...")

        worker = UniverseSyncWorker()
        page._sync_worker = worker

        def on_finished(_path: str) -> None:
            if page._sync_worker is worker:
                page._sync_worker = None
            try:
                if page._finish_cancellable_task(cancelled_message="同步已取消"):
                    return
                page.status_label.setText("A 股列表同步完成")
                page._toast.success("A 股列表同步完成")
                if page._active:
                    page._market_catalog_loaded = False
                    page._market_page_cache.clear()
                    page._market_count_cache.clear()
                    self.load_stock_list()
            finally:
                page._release_worker(worker)

        def on_failed(msg: str) -> None:
            if page._sync_worker is worker:
                page._sync_worker = None
            try:
                if page._finish_cancellable_task(cancelled_message="同步已取消"):
                    return
                page.status_label.setText(f"同步失败: {msg}")
                page._toast.error(msg)
            finally:
                page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
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

    def _sync_market_overview_breadth(self, page) -> None:
        shell = page.parent()
        if shell is None or not hasattr(shell, "overview_controller"):
            return
        controller = shell.overview_controller
        if controller is None or not page._market_catalog:
            return
        rows: list[dict[str, object]] = []
        for item in page._market_catalog:
            quote = page._market_catalog_quotes.get(item.tickflow_symbol)
            if quote is None:
                continue
            rows.append(
                {
                    "change_pct": quote.change_pct,
                    "amount": quote.amount,
                    "vt_symbol": item.vt_symbol,
                }
            )
        controller.apply_market_snapshot(rows, updated_at=page._market_updated_at)

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
