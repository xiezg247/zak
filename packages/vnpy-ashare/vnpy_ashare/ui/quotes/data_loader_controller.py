"""看盘页列表与市场榜数据加载。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.data.bar_access import universe_exists
from vnpy_ashare.app.engine_access import get_bar_service
from vnpy_ashare.ui.quotes.workers import (
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
        self.load_market_page(quiet=False)

    def load_market_page(self, *, quiet: bool = False) -> None:
        page = self._p
        if not page._active or not page.config.use_market_rank:
            return

        if not self._universe_exists():
            page.display_stocks = []
            page.quote_table_model.set_row_count(0)
            page._market_total = 0
            page._pagination.update_controls()
            page.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        if page._thread_active(page._market_worker):
            return

        page._load_generation += 1
        generation = page._load_generation
        keyword = page.search_edit.text().strip()
        if quiet:
            if page._thread_active(page._quotes_worker):
                return
        else:
            page._set_busy(True)
            page.status_label.setText("正在加载市场数据...")

        worker = MarketPageLoadWorker(
            keyword=keyword,
            page=page._market_page,
            page_size=page.config.market_page_size,
            board=page._market_board,
        )
        page._market_worker = worker

        def on_finished(result: object) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            if generation != page._load_generation or not page._active:
                return
            if not isinstance(result, MarketPageResult):
                return

            page.display_stocks = result.items
            page.quote_map = dict(result.quotes)
            page._market_total = result.total
            page._apply_default_table_sort = True
            self.sync_market_quotes_to_cache(result)
            if not quiet:
                page._set_busy(False)
            page._render_table()
            page._pagination.update_controls()
            page.status_label.setText(page._pagination.format_status(result))
            page._update_quote_source_label()

            if page.config.auto_refresh_quotes:
                page._quote_timer.start()
            else:
                page._quote_timer.stop()

        def on_failed(msg: str) -> None:
            if page._market_worker is worker:
                page._market_worker = None
            if generation != page._load_generation or not page._active:
                return
            if not quiet:
                page._set_busy(False)
                page.status_label.setText(f"加载失败: {msg}")

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

        page._set_busy(True)
        page.status_label.setText(f"正在加载{page.page_name}...")
        page.quote_table_model.set_row_count(0)

        worker = UniverseLoadWorker(scope_key, local_scope=page._local_scope)
        page._load_worker = worker

        def on_finished(stocks: list) -> None:
            if page._load_worker is worker:
                page._load_worker = None
            if generation != page._load_generation or not page._active:
                return
            page.all_stocks = stocks
            page._set_busy(False)
            page.apply_filter()

        def on_failed(msg: str) -> None:
            if page._load_worker is worker:
                page._load_worker = None
            if generation != page._load_generation or not page._active:
                return
            page._set_busy(False)
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

    def _universe_exists(self) -> bool:
        """优先 BarService；无 Engine 时经 bar_access 探测本地 universe 表。"""
        bar_svc = get_bar_service(self._p._get_main_engine())
        if bar_svc is not None:
            return bar_svc.universe_exists()

        return universe_exists()
