"""市场页大盘概览控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore

from vnpy_ashare.ai.context.market_overview import sync_market_overview_context, sync_market_overview_partial
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.market_overview_loaders import MarketOverviewData, build_overview_from_market_rows
from vnpy_ashare.ui.quotes.market_overview.worker import MarketOverviewLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.market_overview.panel import MarketOverviewPanel
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

OVERVIEW_REFRESH_MS = 30_000


class MarketOverviewController(QtCore.QObject):
    def __init__(self, page: QuotesPage, panel: MarketOverviewPanel) -> None:
        super().__init__(page)
        self._page = page
        self._panel = panel
        self._worker: MarketOverviewLoadWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(OVERVIEW_REFRESH_MS)
        self._refresh_timer.timeout.connect(self.refresh)

        panel.index_activated.connect(self._on_index_activated)
        panel.sector_selected.connect(self._on_sector_selected)
        panel.industry_filter_cleared.connect(self._clear_industry_filter)

    def sync_industry_filter(self, industry: str | None) -> None:
        self._panel.set_industry_filter(industry)

    def activate(self) -> None:
        QtCore.QTimer.singleShot(500, self.refresh)
        self._refresh_timer.start()

    def deactivate(self) -> None:
        self._refresh_timer.stop()
        worker = self._worker
        self._worker = None
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def refresh(self) -> None:
        if thread_is_active(self._worker):
            return
        worker = MarketOverviewLoadWorker()
        self._worker = worker

        def on_finished(data: MarketOverviewData) -> None:
            if self._worker is worker:
                self._worker = None
            release_thread(self._retired_workers, worker)
            self._apply_overview(data)

        def on_failed(_msg: str) -> None:
            if self._worker is worker:
                self._worker = None
            release_thread(self._retired_workers, worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def apply_market_snapshot(self, rows: list[dict[str, Any]], *, updated_at: str | None = None) -> None:
        breadth, sectors = build_overview_from_market_rows(rows, updated_at=updated_at)
        if breadth is not None:
            self._panel.apply_breadth(breadth)
        if sectors:
            self._panel.apply_sectors(sectors)
        sync_market_overview_partial(breadth=breadth, sectors=sectors or None)
        self._publish_ai_context()

    def _apply_overview(self, data: MarketOverviewData) -> None:
        self._panel.apply_data(data)
        sync_market_overview_context(data)
        self._publish_ai_context()

    def _publish_ai_context(self) -> None:
        actions = getattr(self._page, "_actions", None)
        if actions is not None:
            actions._publish_ai_context()

    def _on_index_activated(self, vt_symbol: str) -> None:
        from vnpy_ashare.ui.features.stock_analysis import show_stock_analysis_from_quotes_page

        item = parse_stock_symbol(vt_symbol)
        if item is None:
            page_notify(self._page, f"无法解析指数：{vt_symbol}", level="warning")
            return
        quote = self._page.quote_map.get(item.tickflow_symbol)
        show_stock_analysis_from_quotes_page(item=item, page=self._page, quote=quote, parent=self._page)

    def _on_sector_selected(self, industry: str) -> None:
        page = self._page
        if page._market_industry_filter == industry:
            page.set_market_industry_filter(None)
            page.status_label.setText(f"已清除行业筛选：{industry}")
        else:
            page.set_market_industry_filter(industry)
            page.status_label.setText(f"行业筛选：{industry}（再次双击该行业可清除）")

    def _clear_industry_filter(self) -> None:
        page = self._page
        if not page._market_industry_filter:
            return
        previous = page._market_industry_filter
        page.set_market_industry_filter(None)
        page.status_label.setText(f"已清除行业筛选：{previous}")
