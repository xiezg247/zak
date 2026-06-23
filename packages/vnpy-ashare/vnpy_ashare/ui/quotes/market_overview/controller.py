"""市场页大盘概览控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context.market_overview import (
    sync_emotion_cycle_context,
    sync_market_overview_context,
    sync_market_overview_partial,
)
from vnpy_ashare.app.engine_access import get_ashare_engine
from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label, is_ashare_trading_session
from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle, store_emotion_cycle_snapshot
from vnpy_ashare.quotes.market.emotion_cycle_cache import peek_emotion_cycle_snapshot
from vnpy_ashare.quotes.market.emotion_cycle_inputs import build_emotion_cycle_inputs
from vnpy_ashare.quotes.market.market_overview_cache import invalidate_market_overview_cache, peek_market_overview_data
from vnpy_ashare.quotes.market.market_overview_loaders import MarketOverviewData, build_overview_from_market_rows, is_market_overview_stale
from vnpy_ashare.ui.quotes.market_overview.worker import MarketOverviewLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.market_overview.panel import MarketOverviewPanel
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

OVERVIEW_REFRESH_MS = 30_000
_OFF_SESSION_EMOTION_TTL_SEC = 86400.0


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
        panel.refresh_requested.connect(self.force_refresh)
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
        intraday = is_ashare_trading_session()
        peeked = peek_market_overview_data(intraday=intraday)
        self._apply_peeked_overview(intraday=intraday)
        if intraday:
            QtCore.QTimer.singleShot(500, self.refresh)
        elif peeked is None or is_market_overview_stale(peeked):
            QtCore.QTimer.singleShot(500, self.force_refresh)
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
        self._start_overview_load(force=False)

    def force_refresh(self) -> None:
        """手动或过期快照：跳过盘外 peek 短路并重拉环境指标。"""
        self._start_overview_load(force=True)

    def _start_overview_load(self, *, force: bool) -> None:
        if thread_is_active(self._worker):
            return
        intraday = is_ashare_trading_session()
        if not intraday and not force:
            peeked = peek_market_overview_data(intraday=False)
            if peeked is not None:
                self._apply_overview(peeked, intraday=False)
                return
        if force:
            invalidate_market_overview_cache()
        self._panel.set_overview_refreshing(True)
        worker = MarketOverviewLoadWorker(intraday=intraday, force=force)
        self._worker = worker

        def on_finished(data: MarketOverviewData) -> None:
            if self._worker is worker:
                self._worker = None
            release_thread(self._retired_workers, worker)
            self._panel.set_overview_refreshing(False)
            self._apply_overview(data, intraday=intraday)

        def on_failed(_msg: str) -> None:
            if self._worker is worker:
                self._worker = None
            release_thread(self._retired_workers, worker)
            self._panel.set_overview_refreshing(False)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _refresh_off_session(self) -> None:
        self.force_refresh()

    def _apply_peeked_overview(self, *, intraday: bool) -> None:
        peeked = peek_market_overview_data(intraday=intraday)
        if peeked is not None:
            self._apply_overview(peeked, intraday=intraday, from_peek=True)
        emotion_ttl = 30.0 if intraday else _OFF_SESSION_EMOTION_TTL_SEC
        peeked_emotion = peek_emotion_cycle_snapshot(max_age_sec=emotion_ttl)
        if peeked_emotion is not None:
            self._panel.apply_emotion_cycle(peeked_emotion)

    def apply_market_snapshot(self, rows: list[dict[str, Any]], *, updated_at: str | None = None) -> None:
        intraday = is_ashare_trading_session()
        breadth, sectors = build_overview_from_market_rows(rows, updated_at=updated_at)
        session_note = f"{ashare_market_phase_label()} · " if not intraday and breadth is not None else ""
        if breadth is not None and intraday:
            self._panel.apply_breadth(breadth, session_note=session_note)
            self._apply_emotion_cycle(breadth)
        if sectors:
            self._panel.apply_sectors(sectors)
        sync_market_overview_partial(
            breadth=breadth if intraday else None,
            sectors=sectors or None,
        )
        self._publish_ai_context()

    def _apply_overview(
        self,
        data: MarketOverviewData,
        *,
        intraday: bool | None = None,
        from_peek: bool = False,
    ) -> None:
        if intraday is None:
            intraday = is_ashare_trading_session()
        session_note = ""
        if not intraday and data.breadth is not None:
            session_note = f"{ashare_market_phase_label()} · "
        self._panel.apply_data(data, session_note=session_note)
        if data.breadth is not None and intraday and not from_peek:
            self._apply_emotion_cycle(data.breadth)
        sync_market_overview_context(data)
        self._publish_ai_context()

    def _apply_emotion_cycle(self, breadth) -> None:
        inputs = build_emotion_cycle_inputs(breadth)
        snapshot = classify_emotion_cycle(inputs)
        store_emotion_cycle_snapshot(snapshot)
        self._panel.apply_emotion_cycle(snapshot)
        sync_emotion_cycle_context(snapshot)

        main_engine = self._page._get_main_engine()
        engine = get_ashare_engine(main_engine)
        if engine is None:
            return
        service = engine.notification_service
        if service is not None:
            service.publish_emotion_cycle(inputs)

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
        if not page._market_industry_filter and not page._market_vt_whitelist:
            return
        previous = page._market_industry_filter or page._market_drilldown_label or "筛选"
        if hasattr(page, "clear_market_drilldown_filters"):
            page.clear_market_drilldown_filters()
        else:
            page.set_market_industry_filter(None)
        page.status_label.setText(f"已清除筛选：{previous}")

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
