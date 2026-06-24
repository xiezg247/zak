"""板块资金 Controller 共享常量与状态。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookBundle,
    SectorFlowRotationSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import load_sector_flow_outlook_strategy_class
from vnpy_ashare.services.sector_flow import SectorFlowService
from vnpy_ashare.ui.sector_flow.leaders_worker import SectorLeadersLoadWorker
from vnpy_ashare.ui.sector_flow.outlook_worker import SectorFlowOutlookLoadWorker
from vnpy_ashare.ui.sector_flow.rotation_worker import SectorFlowRotationLoadWorker
from vnpy_ashare.ui.sector_flow.sector_strategy_worker import SectorFlowSectorStrategyWorker
from vnpy_ashare.ui.sector_flow.worker import SectorFlowLoadWorker
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.ui.sector_flow.page import SectorFlowPageWidget

DEFAULT_REFRESH_MS = 30_000
TAB_OVERVIEW = 0
TAB_INFLOW = 1
TAB_OUTFLOW = 2
TAB_DIVERGENCE = 3
TAB_ROTATION = 4
TAB_OUTLOOK = 5


class SectorFlowControllerBase(QtCore.QObject):
    def __init__(self, page: SectorFlowPageWidget, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(page)
        self._page = page
        self._main_engine = main_engine
        self._event_engine = event_engine
        self._panel = page.panel
        self._worker: SectorFlowLoadWorker | None = None
        self._rotation_worker: SectorFlowRotationLoadWorker | None = None
        self._outlook_worker: SectorFlowOutlookLoadWorker | None = None
        self._sector_strategy_worker: SectorFlowSectorStrategyWorker | None = None
        self._sector_strategy_queue: list[SectorFlowRow] = []
        self._sector_strategy_batch_total = 0
        self._sector_strategy_batch_succeeded = 0
        self._sector_strategy_batch_failed = 0
        self._sector_strategy_batch_aligned = 0
        self._sector_strategy_batch_diverged = 0
        self._sector_strategy_batch_scanned_ids: set[str] = set()
        self._leaders_worker: SectorLeadersLoadWorker | None = None
        self._retired: list[QtCore.QThread] = []
        self._last_snapshot: SectorFlowSnapshot | None = None
        self._last_rotation: SectorFlowRotationSnapshot | None = None
        self._last_outlook: SectorFlowOutlookBundle | None = None
        self._outlook_strategy_class = load_sector_flow_outlook_strategy_class()
        self._pending_focus: set[str] = set()
        self._pending_view_tab: int | None = None
        self._sector_kind = "industry"
        self._service: SectorFlowService | None = None

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)

        panel = self._panel
        panel.refresh_requested.connect(self.refresh)
        panel.ai_requested.connect(self._request_ai)
        panel.sector_kind_changed.connect(self._on_sector_kind_changed)
        panel.view_tab_changed.connect(self._on_view_tab_changed)
        panel.table.sector_activated.connect(self._on_sector_activated)
        panel.table.sector_selected.connect(self._on_sector_selected)
        panel.rotation_table.sector_activated.connect(self._on_sector_activated)
        panel.rotation_table.sector_selected.connect(self._on_sector_selected)
        panel.rotation_table.detail_requested.connect(self._on_rotation_detail_requested)
        panel.rotation_table.sector_strategy_scan_requested.connect(self._on_sector_strategy_scan_requested)
        panel.outlook_table.sector_activated.connect(self._on_sector_activated)
        panel.outlook_table.sector_selected.connect(self._on_sector_selected)
        panel.outlook_table.detail_requested.connect(self._on_outlook_detail_requested)
        panel.outlook_table.sector_strategy_scan_requested.connect(self._on_sector_strategy_scan_requested)
        panel.outlook_table.batch_strategy_scan_requested.connect(self._on_outlook_batch_strategy_scan_requested)
        panel.outlook_table.sector_ai_requested.connect(self._on_sector_ai_requested)
        panel.outlook_strategy_changed.connect(self._on_outlook_strategy_changed)
        panel.outlook_batch_strategy_scan_requested.connect(self._on_outlook_batch_strategy_scan_requested)
        panel.detail.market_drilldown_requested.connect(self._on_detail_market_drilldown)
        panel.detail.screener_requested.connect(self._on_detail_screener)
        panel.detail.radar_leader_requested.connect(self._on_detail_radar_leader)
        panel.detail.radar_sector_theme_requested.connect(self._on_detail_radar_sector_theme)
        panel.detail.leader_screen_requested.connect(self._on_detail_leader_screen)
        panel.sector_overview_selected.connect(self._on_sector_selected)

    def _get_service(self) -> SectorFlowService | None:
        from vnpy_ashare.app.engine_access import get_sector_flow_service

        if self._service is not None:
            return self._service

        service = get_sector_flow_service(self._main_engine)
        if service is not None:
            self._service = service
        return service

    def activate(self) -> None:
        self._publish_ai_context()
        self.refresh()
        self._schedule_timer()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._timer.stop()
        self._session_timer.stop()
        if self._worker is not None:
            self._worker.request_cancel()
            release_thread(self._retired, self._worker, timeout_ms=0)
            self._worker = None
        if self._leaders_worker is not None:
            release_thread(self._retired, self._leaders_worker, timeout_ms=0)
            self._leaders_worker = None
        if self._rotation_worker is not None:
            release_thread(self._retired, self._rotation_worker, timeout_ms=0)
            self._rotation_worker = None
        if self._outlook_worker is not None:
            self._cancel_outlook_worker()
            release_thread(self._retired, self._outlook_worker, timeout_ms=0)
            self._outlook_worker = None
        if self._sector_strategy_worker is not None:
            self._sector_strategy_worker.request_cancel()
            release_thread(self._retired, self._sector_strategy_worker, timeout_ms=0)
            self._sector_strategy_worker = None
        self._sector_strategy_queue.clear()

    def refresh(self) -> None:
        from vnpy_common.ui.feedback import page_notify

        service = self._get_service()
        if service is None:
            page_notify(self._page, "Ashare 引擎未就绪", level="warning")
            return
        if thread_is_active(self._worker):
            return
        worker = SectorFlowLoadWorker(service, sector_kind=self._sector_kind, parent=self._page)
        self._worker = worker
        loading_message = "正在加载概念板块资金…" if self._sector_kind == "concept" else "正在加载行业板块资金…"
        self._panel.set_loading(True, message=loading_message)
        self._page.set_status(loading_message)
        worker.finished.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda _snap, w=worker: self._release_worker(w))
        worker.failed.connect(lambda _msg, w=worker: self._release_worker(w))
        worker.start()

    def _release_worker(self, worker: SectorFlowLoadWorker) -> None:
        if self._worker is worker:
            self._worker = None
        release_thread(self._retired, worker)

    def _update_status_label(self) -> None:
        from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label, is_ashare_trading_session

        phase = ashare_market_phase_label()
        hint = "盘中约30秒刷新" if is_ashare_trading_session() else "非交易时段，已暂停自动刷新"
        self._page.set_status(f"{hint} · 当前{phase}")

    def _on_session_tick(self) -> None:
        self._schedule_timer()
        self._update_status_label()

    def _on_failed(self, message: str) -> None:
        from vnpy_common.ui.feedback import page_notify

        self._panel.set_loading(False)
        page_notify(self._page, f"板块资金加载失败：{message}", level="warning")
        self._page.set_status(message)

    def _schedule_timer(self) -> None:
        from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session

        if is_ashare_trading_session():
            self._timer.start(DEFAULT_REFRESH_MS)
        else:
            self._timer.stop()

    def _on_sector_kind_changed(self, sector_kind: str) -> None:
        self._sector_kind = sector_kind
        self._last_snapshot = None
        self._last_rotation = None
        self._last_outlook = None
        self.refresh()

    def _on_view_tab_changed(self, tab_id: int) -> None:
        if tab_id == TAB_ROTATION:
            if self._last_rotation is not None and self._last_rotation.sector_kind == self._sector_kind:
                self._panel.apply_rotation_snapshot(self._last_rotation)
                first_row = self._panel.rotation_table.selected_sector_row()
                if first_row is None and self._last_rotation.rows:
                    self._panel.rotation_table.selectRow(0)
                return
            self._load_rotation(self._last_snapshot)
            return
        if tab_id == TAB_OUTLOOK:
            if self._last_outlook is not None and self._last_outlook.continuation.sector_kind == self._sector_kind:
                self._panel.apply_outlook_bundle(self._last_outlook)
                return
            self._load_outlook(self._last_snapshot)
            return
        if tab_id == TAB_OVERVIEW and self._last_snapshot is not None:
            service = self._get_service()
            if service is not None:
                overview = service.load_overview_snapshot(self._last_snapshot)
                self._panel.apply_overview_snapshot(overview)
            first = self._panel.table.selected_sector_row()
            if first is None and self._last_snapshot.inflow_rows:
                first = self._last_snapshot.inflow_rows[0]
            if first is not None:
                self._load_sector_leaders(first)
