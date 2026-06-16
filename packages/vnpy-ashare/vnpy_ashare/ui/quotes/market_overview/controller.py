"""市场页大盘概览控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context.market_overview import sync_market_overview_context, sync_market_overview_partial
from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.market.market_overview_loaders import MarketOverviewData, build_overview_from_market_rows
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
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)

        panel.sector_selected.connect(self._on_sector_selected)
        panel.sector_flow_requested.connect(self._open_sector_flow)
        industry_filter = page.industry_filter
        if industry_filter is not None:
            industry_filter.industry_selected.connect(self._on_industry_picker_selected)
            industry_filter.industry_invalid.connect(self._on_industry_picker_invalid)
            industry_filter.industry_cleared.connect(self._clear_industry_filter)

    def sync_industry_filter(self, industry: str | None) -> None:
        self._panel.set_industry_filter(industry)
        industry_filter = self._page.industry_filter
        if industry_filter is not None:
            industry_filter.set_industry(industry)

    def activate(self) -> None:
        industry_filter = self._page.industry_filter
        if industry_filter is not None:
            industry_filter.ensure_options_loaded()
        QtCore.QTimer.singleShot(500, self.refresh)
        self._schedule_timer()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._refresh_timer.stop()
        self._session_timer.stop()
        worker = self._worker
        self._worker = None
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def _on_session_tick(self) -> None:
        self._schedule_timer()

    def _schedule_timer(self) -> None:
        if is_ashare_trading_session():
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

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

    def _on_industry_picker_invalid(self, text: str) -> None:
        page_notify(self._page, f"未找到匹配行业：{text}", level="warning")

    def _on_industry_picker_selected(self, industry: str) -> None:
        label = str(industry or "").strip()
        if not label:
            return
        page = self._page
        page.set_market_industry_filter(label)
        page.status_label.setText(f"行业筛选：{label}（行业 × 可清除）")

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

    def _open_sector_flow(self) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_sector_flow"):
            page_notify(self._page, "无法打开板块资金页", level="warning")
            return
        sector_ids = self._panel.top_sector_industries(limit=6)
        host.open_sector_flow(sector_ids if sector_ids else None)

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        widget: QtWidgets.QWidget | None = self._page
        while widget is not None:
            if hasattr(widget, "open_sector_flow"):
                return widget
            widget = widget.parentWidget()
        return None
