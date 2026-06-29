"""本地 K 线元数据缓存与无效概览清理。"""

from __future__ import annotations

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.services.bar import bar_meta_from_overview, invalidate_bar_overview_cache, iter_bar_overviews
from vnpy_ashare.storage.repositories.bar_overview import fetch_scope_bar_overviews_for_keys
from vnpy_ashare.ui.quotes.controllers.local_data.base import LocalDataControllerBase
from vnpy_ashare.ui.quotes.workers.quotes_workers import InvalidBarCleanupWorker


class LocalDataMetaMixin(LocalDataControllerBase):
    def reset_meta_cache(self, *, invalidate_overview: bool = True) -> None:
        page = self._p
        if invalidate_overview:
            invalidate_bar_overview_cache()
        page.downloaded_keys = set()
        page.bar_meta = {}
        page.bar_list_status = {}

    def ensure_meta_for_items(self, items: list[StockItem]) -> None:
        """按当前页标的批量加载 K 线概览（数据库按 key 查询，不预热全库）。"""
        page = self._p
        if not items:
            return
        keys = [(item.symbol, item.exchange) for item in items]
        overviews = fetch_scope_bar_overviews_for_keys(keys, page._local_scope)
        for item in items:
            key = (item.symbol, item.exchange)
            overview = overviews.get(key)
            if overview is None:
                page.downloaded_keys.discard(key)
                page.bar_meta.pop(key, None)
                page.bar_list_status.pop(key, None)
                continue
            page.downloaded_keys.add(key)
            page.bar_meta[key] = bar_meta_from_overview(overview)

    def refresh_meta(self, *, invalidate_overview: bool = True) -> None:
        page = self._p
        self.reset_meta_cache(invalidate_overview=invalidate_overview)
        if page.config.use_local_pagination:
            self.ensure_meta_for_items(page.all_stocks)
            return
        bar_svc = page._get_bar_service()
        rows = bar_svc.iter_overviews(page._local_scope) if bar_svc else self._fallback_overviews(page._local_scope)
        for row in rows:
            key = (row.symbol, row.exchange)
            page.downloaded_keys.add(key)
            page.bar_meta[key] = bar_meta_from_overview(row)

    @staticmethod
    def _fallback_overviews(scope: str):
        """BarService 不可用时经 bar_access 枚举本地 K 线概览。"""
        return iter_bar_overviews(scope=scope)

    def on_stock_list_loaded(self) -> None:
        """本地列表加载完成后：刷新元数据、重绘表格并恢复当前选中标的图表。"""
        page = self._p
        if not page.config.use_local_table:
            return
        # Worker 在后台按页查询概览；主线程仅批量拉取当前页元数据。
        self.dismiss_gap_check()
        self.refresh_meta(invalidate_overview=False)
        page._local_filter_keyword = page.search_edit.text().strip().lower()
        page._table.apply_local_page_display()

    def schedule_invalid_bar_cleanup(self) -> None:
        """后台清理无效日 K 概览，避免进入本地页时在主线程扫描全库。"""

        page = self._p
        if page._thread_active(getattr(page, "_invalid_bar_cleanup_worker", None)):
            return
        page._wait_worker_release("_invalid_bar_cleanup_worker", timeout_ms=0)

        worker = InvalidBarCleanupWorker()
        page._invalid_bar_cleanup_worker = worker

        def on_finished(removed: object) -> None:
            if page._invalid_bar_cleanup_worker is worker:
                page._invalid_bar_cleanup_worker = None
            try:
                if not page._active or not isinstance(removed, list) or not removed:
                    return
                symbols = "、".join(format_vt_symbol_cn(symbol, exchange) for symbol, exchange in removed[:5])
                suffix = "..." if len(removed) > 5 else ""
                page.status_label.setText(f"已清理 {len(removed)} 条无效日K：{symbols}{suffix}")
                if page.config.use_local_table:
                    page.load_stock_list()
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._invalid_bar_cleanup_worker is worker:
                page._invalid_bar_cleanup_worker = None
            page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()
