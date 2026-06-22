"""板块资金监控控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_quote_service, get_sector_flow_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.market.sector_flow import (
    SectorConstituentRow,
    SectorFlowHistoryPoint,
    SectorFlowOutlookBundle,
    SectorFlowOutlookRow,
    SectorFlowRotationRow,
    SectorFlowRotationSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label, is_ashare_trading_session
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    load_sector_flow_outlook_strategy_class,
    outlook_strategy_label,
    save_sector_flow_outlook_strategy_class,
)
from vnpy_ashare.services.sector_flow import SectorFlowService, format_sector_net_flow_yi
from vnpy_ashare.services.sector_flow_outlook import format_continuation_ai_lines
from vnpy_ashare.services.sector_flow_outlook_strategy import classify_sector_resonance
from vnpy_ashare.services.sector_flow_rotation import format_rotation_ai_lines
from vnpy_ashare.ui.quotes.market_overview.industry_filter_combo import resolve_industry_for_drilldown
from vnpy_ashare.ui.sector_flow.leaders_worker import SectorLeadersLoadWorker
from vnpy_ashare.ui.sector_flow.outlook_batch import (
    coerce_sector_flow_rows,
    format_batch_scan_summary,
    prepare_batch_sector_scans,
)
from vnpy_ashare.ui.sector_flow.outlook_detail_dialog import SectorFlowOutlookDetailDialog
from vnpy_ashare.ui.sector_flow.outlook_worker import SectorFlowOutlookLoadWorker
from vnpy_ashare.ui.sector_flow.rotation_detail_dialog import SectorFlowRotationDetailDialog
from vnpy_ashare.ui.sector_flow.rotation_worker import SectorFlowRotationLoadWorker
from vnpy_ashare.ui.sector_flow.sector_strategy_worker import SectorFlowSectorStrategyWorker
from vnpy_ashare.ui.sector_flow.worker import SectorFlowLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.ui.sector_flow.page import SectorFlowPageWidget

_DEFAULT_REFRESH_MS = 30_000
_TAB_OVERVIEW = 0
_TAB_INFLOW = 1
_TAB_OUTFLOW = 2
_TAB_DIVERGENCE = 3
_TAB_ROTATION = 4
_TAB_OUTLOOK = 5


class SectorFlowController(QtCore.QObject):
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

    def _on_loaded(self, snapshot: SectorFlowSnapshot) -> None:
        self._panel.set_loading(False)
        if not snapshot.rows:
            self._panel.apply_snapshot(snapshot)
            service = self._get_service()
            if service is not None:
                overview = service.load_overview_snapshot(snapshot)
                self._panel.apply_overview_snapshot(overview)
            self._panel.detail.clear()
            status = snapshot.empty_hint or snapshot.updated_at or "暂无数据"
            self._page.set_status(status)
            return
        self._last_snapshot = snapshot
        self._last_rotation = None
        self._last_outlook = None
        self._panel.apply_snapshot(snapshot)
        service = self._get_service()
        if service is not None:
            service.record_overview_sample(snapshot)
            overview = service.load_overview_snapshot(snapshot)
            self._panel.apply_overview_snapshot(overview)
        if self._pending_view_tab is not None:
            tab_id = self._pending_view_tab
            self._pending_view_tab = None
            self._panel.select_view_tab(tab_id, emit=True)
            return
        if self._pending_focus:
            self._panel.focus_sectors(self._pending_focus)
            self._pending_focus.clear()
        self._update_status_label()
        self._publish_ai_context(snapshot)
        if self._panel.active_tab == _TAB_OVERVIEW:
            first_row = None
            if snapshot.inflow_rows:
                first_row = snapshot.inflow_rows[0]
            elif snapshot.outflow_rows:
                first_row = snapshot.outflow_rows[0]
            if first_row is not None:
                self._load_sector_leaders(first_row)
            return
        if self._panel.active_tab == _TAB_ROTATION:
            self._load_rotation(snapshot)
            return
        if self._panel.active_tab == _TAB_OUTLOOK:
            self._load_outlook(snapshot)
            return
        first_row = self._panel.table.selected_sector_row()
        if first_row is None and snapshot.inflow_rows:
            self._panel.table.selectRow(0)
            first_row = self._panel.table.selected_sector_row()
        if first_row is not None:
            self._load_sector_leaders(first_row)

    def _on_sector_selected(self, sector: SectorFlowRow) -> None:
        if self._panel.active_tab in {_TAB_ROTATION, _TAB_OUTLOOK}:
            return
        self._load_sector_leaders(sector)

    def _on_rotation_detail_requested(self, rotation_row: object) -> None:
        if not isinstance(rotation_row, SectorFlowRotationRow):
            return
        dialog = SectorFlowRotationDetailDialog(rotation_row, parent=self._page)
        dialog.market_drilldown_requested.connect(self._on_detail_market_drilldown)
        dialog.exec()

    def _on_outlook_detail_requested(self, payload: object) -> None:
        if not isinstance(payload, SectorFlowOutlookRow):
            return
        dialog = SectorFlowOutlookDetailDialog(payload, parent=self._page)
        dialog.market_drilldown_requested.connect(self._on_detail_market_drilldown)
        dialog.exec()

    def _load_sector_leaders(self, sector: SectorFlowRow) -> None:
        service = self._get_service()
        if service is None:
            return
        if thread_is_active(self._leaders_worker):
            return
        self._panel.detail.set_loading(sector.name)
        worker = SectorLeadersLoadWorker(service, sector, parent=self._page)
        self._leaders_worker = worker
        worker.finished.connect(self._on_leaders_loaded)
        worker.finished.connect(lambda _sector, _result, _history, w=worker: self._release_leaders_worker(w))
        worker.start()

    def _release_leaders_worker(self, worker: SectorLeadersLoadWorker) -> None:
        if self._leaders_worker is worker:
            self._leaders_worker = None
        release_thread(self._retired, worker)

    def _on_leaders_loaded(self, sector: SectorFlowRow, result: object, history: object) -> None:
        if isinstance(result, Exception):
            self._panel.detail.show_sector(sector, [], history=[] if not isinstance(history, list) else history)
            return
        leaders = result if isinstance(result, list) else []
        typed: list[SectorConstituentRow] = [item for item in leaders if isinstance(item, SectorConstituentRow)]
        history_rows: list[SectorFlowHistoryPoint] = [
            item for item in (history if isinstance(history, list) else []) if isinstance(item, SectorFlowHistoryPoint)
        ]
        self._panel.detail.show_sector(sector, typed, history=history_rows)

    def _on_detail_market_drilldown(self, sector: SectorFlowRow) -> None:
        host = self._find_main_window()
        if host is None:
            page_notify(self._page, "无法打开市场页", level="warning")
            return
        if sector.sector_kind == "concept":
            service = self._get_service()
            if service is None or not hasattr(host, "open_market_concept_drilldown"):
                page_notify(self._page, "无法打开市场页概念筛选", level="warning")
                return
            vt_symbols = service.resolve_concept_vt_symbols(sector)
            if not vt_symbols:
                page_notify(self._page, f"未找到概念「{sector.name}」成分映射", level="warning")
                return
            host.open_market_concept_drilldown(sector.name, vt_symbols)
            return
        if hasattr(host, "open_market_industry_filter"):
            industry = (
                resolve_industry_for_drilldown(
                    sector.name,
                    sector_id=sector.sector_id,
                )
                or str(sector.name or "").strip()
            )
            if not industry:
                page_notify(self._page, f"未找到行业「{sector.name}」映射", level="warning")
                return
            host.open_market_industry_filter(industry)
            return
        page_notify(self._page, "无法打开市场页行业筛选", level="warning")

    def _on_detail_screener(self, industry: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_industry"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        host.open_screener_industry(industry)

    def _on_detail_radar_leader(self) -> None:
        sector = self._panel.detail.current_sector()
        if sector is None:
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_radar_card"):
            page_notify(self._page, "无法打开雷达页", level="warning")
            return
        host.open_radar_card("leader_pick", refresh=True)
        self._page.set_status(f"已打开雷达·龙头 · {sector.name}")

    def _on_detail_radar_sector_theme(self) -> None:
        sector = self._panel.detail.current_sector()
        if sector is None or sector.sector_kind != "industry":
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_radar_card"):
            page_notify(self._page, "无法打开雷达页", level="warning")
            return
        host.open_radar_card("sector_theme", variant="leaders_tiered", refresh=True)
        self._page.set_status(f"已打开雷达·主线 · {sector.name}")

    def _on_detail_leader_screen(self) -> None:
        sector = self._panel.detail.current_sector()
        if sector is None:
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_radar_leader_loop"):
            page_notify(self._page, "无法打开龙头选股", level="warning")
            return
        host.open_radar_leader_loop(run_leader_screen=True)
        self._page.set_status(f"已打开龙头选股 · {sector.name}")

    def _update_status_label(self) -> None:
        phase = ashare_market_phase_label()
        hint = "盘中约30秒刷新" if is_ashare_trading_session() else "非交易时段，已暂停自动刷新"
        self._page.set_status(f"{hint} · 当前{phase}")

    def _on_session_tick(self) -> None:
        self._schedule_timer()
        self._update_status_label()

    def _on_failed(self, message: str) -> None:
        self._panel.set_loading(False)
        page_notify(self._page, f"板块资金加载失败：{message}", level="warning")
        self._page.set_status(message)

    def _schedule_timer(self) -> None:
        if is_ashare_trading_session():
            self._timer.start(_DEFAULT_REFRESH_MS)
        else:
            self._timer.stop()

    def _on_sector_kind_changed(self, sector_kind: str) -> None:
        self._sector_kind = sector_kind
        self._last_snapshot = None
        self._last_rotation = None
        self._last_outlook = None
        self.refresh()

    def _on_view_tab_changed(self, tab_id: int) -> None:
        if tab_id == _TAB_ROTATION:
            if self._last_rotation is not None and self._last_rotation.sector_kind == self._sector_kind:
                self._panel.apply_rotation_snapshot(self._last_rotation)
                first_row = self._panel.rotation_table.selected_sector_row()
                if first_row is None and self._last_rotation.rows:
                    self._panel.rotation_table.selectRow(0)
                return
            self._load_rotation(self._last_snapshot)
            return
        if tab_id == _TAB_OUTLOOK:
            if self._last_outlook is not None and self._last_outlook.continuation.sector_kind == self._sector_kind:
                self._panel.apply_outlook_bundle(self._last_outlook)
                return
            self._load_outlook(self._last_snapshot)
            return
        if tab_id == _TAB_OVERVIEW and self._last_snapshot is not None:
            service = self._get_service()
            if service is not None:
                overview = service.load_overview_snapshot(self._last_snapshot)
                self._panel.apply_overview_snapshot(overview)
            first = self._panel.table.selected_sector_row()
            if first is None and self._last_snapshot.inflow_rows:
                first = self._last_snapshot.inflow_rows[0]
            if first is not None:
                self._load_sector_leaders(first)

    def _load_rotation(self, snapshot: SectorFlowSnapshot | None = None) -> None:
        service = self._get_service()
        if service is None:
            return
        if thread_is_active(self._rotation_worker):
            return
        self._panel.set_loading(True, message="正在加载近15日板块轮动…")
        worker = SectorFlowRotationLoadWorker(
            service,
            snapshot=snapshot,
            sector_kind=self._sector_kind,
            parent=self._page,
        )
        self._rotation_worker = worker
        worker.finished.connect(self._on_rotation_loaded)
        worker.failed.connect(self._on_rotation_failed)
        worker.finished.connect(lambda _snap, w=worker: self._release_rotation_worker(w))
        worker.failed.connect(lambda _msg, w=worker: self._release_rotation_worker(w))
        worker.start()

    def _release_rotation_worker(self, worker: SectorFlowRotationLoadWorker) -> None:
        if self._rotation_worker is worker:
            self._rotation_worker = None
        release_thread(self._retired, worker)

    def _on_rotation_loaded(self, rotation: object) -> None:
        self._panel.set_loading(False)
        if not isinstance(rotation, SectorFlowRotationSnapshot):
            return
        self._last_rotation = rotation
        self._panel.apply_rotation_snapshot(rotation)
        self._update_status_label()
        self._publish_ai_context(self._last_snapshot)
        if self._pending_focus:
            self._panel.focus_sectors(self._pending_focus)
            self._pending_focus.clear()
            return
        first_row = self._panel.rotation_table.selected_rotation_row()
        if first_row is None and rotation.rows:
            self._panel.rotation_table.selectRow(0)
        elif rotation.empty_hint:
            self._page.set_status(rotation.empty_hint)

    def _outlook_strategy_label(self) -> str:
        try:
            text = str(self._panel._outlook_strategy_combo.currentText() or "").strip()
        except (AttributeError, RuntimeError):
            text = ""
        if text:
            return text
        return outlook_strategy_label(self._outlook_strategy_class)

    def _cancel_outlook_worker(self) -> None:
        worker = self._outlook_worker
        if worker is None:
            return
        worker.request_cancel()

    def _load_outlook(self, snapshot: SectorFlowSnapshot | None = None) -> None:
        service = self._get_service()
        if service is None:
            return
        if thread_is_active(self._outlook_worker):
            self._cancel_outlook_worker()
        self._panel.set_loading(True, message="正在加载未来3日延续展望…")
        worker = SectorFlowOutlookLoadWorker(
            service,
            snapshot=snapshot,
            sector_kind=self._sector_kind,
            parent=self._page,
        )
        self._outlook_worker = worker
        worker.finished.connect(self._on_outlook_loaded)
        worker.failed.connect(self._on_outlook_failed)
        worker.finished.connect(lambda _bundle, w=worker: self._release_outlook_worker(w))
        worker.failed.connect(lambda _msg, w=worker: self._release_outlook_worker(w))
        worker.start()

    def _release_outlook_worker(self, worker: SectorFlowOutlookLoadWorker) -> None:
        if self._outlook_worker is worker:
            self._outlook_worker = None
        release_thread(self._retired, worker)

    def _on_outlook_loaded(self, bundle: object) -> None:
        worker = self.sender()
        if isinstance(worker, SectorFlowOutlookLoadWorker) and worker is not self._outlook_worker:
            return
        self._panel.set_loading(False)
        if not isinstance(bundle, SectorFlowOutlookBundle):
            return
        self._last_outlook = bundle
        self._panel.apply_outlook_bundle(bundle)
        self._update_status_label()
        self._publish_ai_context(self._last_snapshot)
        if self._pending_focus:
            self._panel.focus_sectors(self._pending_focus)
            self._pending_focus.clear()
            return
        if bundle.continuation.empty_hint:
            self._page.set_status(bundle.continuation.empty_hint)

    def _on_outlook_failed(self, message: str) -> None:
        worker = self.sender()
        if isinstance(worker, SectorFlowOutlookLoadWorker) and worker is not self._outlook_worker:
            return
        self._panel.set_loading(False)
        if not str(message or "").strip():
            return
        page_notify(self._page, f"板块展望加载失败：{message}", level="warning")
        self._page.set_status(message)

    def _on_outlook_strategy_changed(self, class_name: str) -> None:
        normalized = str(class_name or "").strip()
        if not normalized or normalized == self._outlook_strategy_class:
            return
        save_sector_flow_outlook_strategy_class(normalized)
        self._outlook_strategy_class = normalized
        if self._panel.active_tab != _TAB_OUTLOOK:
            return
        self._panel.clear_outlook_sector_scans()
        self._publish_ai_context(self._last_snapshot)

    def _continuation_row_for_sector(self, sector: SectorFlowRow) -> SectorFlowOutlookRow | None:
        bundle = self._last_outlook
        if bundle is None:
            return None
        for row in bundle.continuation.rows:
            if row.sector.sector_id == sector.sector_id:
                return row
        return None

    def _on_sector_strategy_scan_requested(self, sector: object) -> None:
        if not isinstance(sector, SectorFlowRow):
            return
        self._on_outlook_batch_strategy_scan_requested([sector])

    def _on_outlook_batch_strategy_scan_requested(self, sectors: object) -> None:
        if thread_is_active(self._sector_strategy_worker) or self._sector_strategy_queue:
            page_notify(self._page, "正在扫描板块，请稍候", level="info")
            return
        candidates = coerce_sector_flow_rows(sectors)
        queue, hint = prepare_batch_sector_scans(candidates)
        if not queue:
            page_notify(self._page, hint or "请先选择板块", level="info")
            return
        if hint:
            page_notify(self._page, hint, level="info")
        self._sector_strategy_queue = list(queue)
        self._sector_strategy_batch_total = len(queue)
        self._sector_strategy_batch_succeeded = 0
        self._sector_strategy_batch_failed = 0
        self._sector_strategy_batch_aligned = 0
        self._sector_strategy_batch_diverged = 0
        self._sector_strategy_batch_scanned_ids = set()
        self._start_next_sector_strategy_scan()

    def _start_next_sector_strategy_scan(self) -> None:
        processed = self._sector_strategy_batch_succeeded + self._sector_strategy_batch_failed
        if processed >= self._sector_strategy_batch_total > 0:
            self._finish_sector_strategy_batch()
            return
        if not self._sector_strategy_queue:
            self._finish_sector_strategy_batch()
            return
        sector = self._sector_strategy_queue.pop(0)
        bundle = self._last_outlook
        forward_dates = bundle.continuation.forward_dates if bundle is not None else ()
        label = self._outlook_strategy_label()
        current = self._sector_strategy_batch_succeeded + self._sector_strategy_batch_failed + 1
        total = self._sector_strategy_batch_total
        if total > 1:
            message = f"正在扫描 ({current}/{total}) 「{sector.name}」· {label}…"
        else:
            message = f"正在扫描「{sector.name}」· {label}…"
        self._panel.set_loading(True, message=message)
        worker = SectorFlowSectorStrategyWorker(
            sector,
            strategy_class=self._outlook_strategy_class,
            forward_dates=forward_dates,
            parent=self._page,
        )
        self._sector_strategy_worker = worker
        worker.scan_finished.connect(self._on_sector_strategy_scanned)
        worker.failed.connect(self._on_sector_strategy_failed)
        worker.scan_finished.connect(lambda _row, w=worker: self._release_sector_strategy_worker(w))
        worker.failed.connect(lambda _msg, w=worker: self._release_sector_strategy_worker(w))
        worker.start()

    def _finish_sector_strategy_batch(self) -> None:
        self._panel.set_loading(False)
        total = self._sector_strategy_batch_total
        if total <= 0:
            return
        if total == 1 and self._sector_strategy_batch_succeeded == 1:
            return
        if self._sector_strategy_batch_succeeded <= 0 and self._sector_strategy_batch_failed <= 0:
            return
        msg = format_batch_scan_summary(
            total=total,
            succeeded=self._sector_strategy_batch_succeeded,
            failed=self._sector_strategy_batch_failed,
            aligned=self._sector_strategy_batch_aligned,
            diverged=self._sector_strategy_batch_diverged,
        )
        self._page.set_status(msg)
        level = "success" if self._sector_strategy_batch_failed == 0 else "warning"
        page_notify(self._page, msg, level=level)
        if self._sector_strategy_batch_scanned_ids:
            self._panel.focus_sectors(set(self._sector_strategy_batch_scanned_ids))
        self._sector_strategy_batch_total = 0
        self._sector_strategy_batch_scanned_ids = set()
        self._publish_ai_context(self._last_snapshot)

    def _release_sector_strategy_worker(self, worker: SectorFlowSectorStrategyWorker) -> None:
        if self._sector_strategy_worker is worker:
            self._sector_strategy_worker = None
        release_thread(self._retired, worker)

    def _on_sector_strategy_scanned(self, row: object) -> None:
        if not isinstance(row, SectorFlowOutlookRow):
            return
        service = self._get_service()
        if service is None:
            self._finish_sector_strategy_batch()
            return
        if self._last_outlook is None:
            self._sector_strategy_queue.clear()
            self._finish_sector_strategy_batch()
            self._load_outlook(self._last_snapshot)
            return
        self._last_outlook = service.merge_sector_scan(self._last_outlook, row)
        self._panel.apply_outlook_bundle(self._last_outlook)
        if self._panel.active_tab != _TAB_OUTLOOK:
            self._panel.select_view_tab(_TAB_OUTLOOK, emit=True)
        self._sector_strategy_batch_succeeded += 1
        self._sector_strategy_batch_scanned_ids.add(row.sector.sector_id)
        resonance = classify_sector_resonance(self._continuation_row_for_sector(row.sector), row)
        if resonance == "同向":
            self._sector_strategy_batch_aligned += 1
        elif resonance == "背离":
            self._sector_strategy_batch_diverged += 1
        if self._sector_strategy_batch_total <= 1:
            self._panel.set_loading(False)
            self._panel.focus_sectors({row.sector.sector_id})
            msg = f"「{row.sector.name}」策略扫描完成 · T+1 {row.days[0].bias if row.days else '—'} · 共振 {resonance}"
            self._page.set_status(msg)
            page_notify(self._page, msg, level="success")
            self._sector_strategy_batch_total = 0
            self._sector_strategy_batch_scanned_ids = set()
            self._publish_ai_context(self._last_snapshot)
            return
        if self._sector_strategy_queue:
            self._start_next_sector_strategy_scan()
            return
        self._finish_sector_strategy_batch()

    def _on_sector_strategy_failed(self, message: str) -> None:
        self._sector_strategy_batch_failed += 1
        if self._sector_strategy_queue:
            if str(message or "").strip():
                self._page.set_status(message)
            self._start_next_sector_strategy_scan()
            return
        self._finish_sector_strategy_batch()
        if not str(message or "").strip():
            return
        if self._sector_strategy_batch_total <= 1:
            page_notify(self._page, f"板块策略扫描失败：{message}", level="warning")
        self._page.set_status(message)

    def _on_sector_ai_requested(self, sector: object) -> None:
        if not isinstance(sector, SectorFlowRow):
            return
        snap = self._last_snapshot
        if snap is None or not snap.rows:
            page_notify(self._page, "请先刷新板块数据", level="warning")
            return
        if self._event_engine is None:
            return
        continuation = self._continuation_row_for_sector(sector)
        scan_row = None
        if self._last_outlook is not None:
            for item in self._last_outlook.sector_scans:
                if item.sector.sector_id == sector.sector_id:
                    scan_row = item
                    break
        kind_label = "概念" if sector.sector_kind == "concept" else "行业"
        strategy_label = self._outlook_strategy_label()
        lines = [
            f"请解读「{sector.name}」{kind_label}板块的资金延续与策略信号（统计情景，非资金预测）。",
            f"策略口径：{strategy_label}（成分股直扫，非雷达全球展望池）。",
        ]
        if continuation is not None:
            day_tags = " / ".join(f"T+{index + 1}{day.bias}({day.strength:.2f})" for index, day in enumerate(continuation.days))
            lines.append(f"资金延续：{continuation.headline_pattern} {day_tags} — {continuation.rationale}")
        else:
            lines.append("资金延续：暂无加载数据")
        if scan_row is not None:
            day_tags = " / ".join(f"T+{index + 1}{day.bias}({day.strength:.2f})" for index, day in enumerate(scan_row.days))
            resonance = classify_sector_resonance(continuation, scan_row)
            lines.append(f"成分策略：{scan_row.headline_pattern} {day_tags} — {scan_row.rationale}")
            lines.append(f"延续与策略 T+1 共振：{resonance}")
        else:
            lines.append("成分策略：尚未扫描，请说明仅可基于资金延续解读")
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt="\n".join(lines), source_page="板块资金"),
            )
        )

    def _on_rotation_failed(self, message: str) -> None:
        self._panel.set_loading(False)
        page_notify(self._page, f"板块轮动加载失败：{message}", level="warning")
        self._page.set_status(message)

    def focus_sectors(
        self,
        sector_ids: list[str],
        *,
        tab: str = "default",
        sector_kind: str | None = None,
    ) -> None:
        cleaned = {name.strip() for name in sector_ids if name and name.strip()}
        tab_map = {
            "default": _TAB_OVERVIEW,
            "overview": _TAB_OVERVIEW,
            "inflow": _TAB_INFLOW,
            "outflow": _TAB_OUTFLOW,
            "divergence": _TAB_DIVERGENCE,
            "rotation": _TAB_ROTATION,
            "outlook": _TAB_OUTLOOK,
        }
        pending_tab = tab_map.get(tab, _TAB_OVERVIEW)
        self._pending_view_tab = pending_tab
        if sector_kind in {"industry", "concept"}:
            self._sector_kind = sector_kind
            self._panel.select_sector_kind(sector_kind, emit=False)
        elif tab not in {"rotation", "outlook"}:
            self._sector_kind = "industry"
            self._panel.select_sector_kind("industry", emit=False)
        if cleaned:
            self._pending_focus = cleaned
        if self._last_snapshot and self._last_snapshot.rows and self._last_snapshot.sector_kind == self._sector_kind:
            self._panel.select_view_tab(pending_tab, emit=True)
            if cleaned:
                self._panel.focus_sectors(cleaned)
            return
        self.refresh()

    def _on_sector_activated(self, industry: str) -> None:
        if self._panel.active_tab == _TAB_ROTATION:
            sector = self._panel.rotation_table.selected_sector_row()
        elif self._panel.active_tab == _TAB_OUTLOOK:
            sector = self._panel.outlook_table.selected_sector_row()
        else:
            sector = self._panel.table.selected_sector_row()
        if sector is not None and sector.sector_kind == "concept":
            self._on_detail_market_drilldown(sector)
            return
        if self._sector_kind == "concept":
            page_notify(self._page, "概念板块请使用右侧「市场成分」或单击选中后操作", level="info")
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_market_industry_filter"):
            page_notify(self._page, "无法打开市场页行业筛选", level="warning")
            return
        if sector is not None and sector.sector_kind == "industry":
            label = resolve_industry_for_drilldown(sector.name, sector_id=sector.sector_id) or sector.name
        else:
            label = resolve_industry_for_drilldown(industry) or industry
        if not label:
            page_notify(self._page, f"未找到行业「{industry}」映射", level="warning")
            return
        host.open_market_industry_filter(label)

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        widget: QtWidgets.QWidget | None = self._page
        while widget is not None:
            if (
                hasattr(widget, "open_market_industry_filter")
                or hasattr(widget, "open_market_concept_drilldown")
                or hasattr(widget, "open_screener_industry")
                or hasattr(widget, "open_radar_card")
            ):
                return widget
            widget = widget.parentWidget()
        return None

    def _publish_ai_context(self, snapshot: SectorFlowSnapshot | None = None) -> None:
        quote_service = get_quote_service(self._main_engine)
        if quote_service is None:
            return
        extra_lines = ["板块资金监控页"]
        snap = snapshot or self._last_snapshot
        if snap and snap.rows:
            kind_label = "概念" if snap.sector_kind == "concept" else "行业"
            mode_labels = {"intraday": "盘中估算", "official_dc": "日终东财", "official_ths": "日终同花顺", "official_sw": "日终申万"}
            extra_lines.append(f"{kind_label}·{mode_labels.get(snap.data_mode, snap.data_mode)}")
            extra_lines.append(
                f"净流入 {snap.top_inflow_name} {format_sector_net_flow_yi(snap.top_inflow_yi)}；"
                f"净流出 {snap.top_outflow_name} {format_sector_net_flow_yi(snap.top_outflow_yi)}"
            )
            rotation = self._last_rotation
            if rotation and rotation.rows:
                extra_lines.extend(format_rotation_ai_lines(rotation, limit=5))
            outlook = self._last_outlook
            if outlook and outlook.continuation.rows:
                extra_lines.extend(format_continuation_ai_lines(outlook.continuation, limit=5))
            for row in snap.rows[:8]:
                leader = f" 龙头{row.leader_stock}" if row.leader_stock else ""
                extra_lines.append(f"{row.name} 强度{row.strength:.1f} 涨幅{row.change_pct:+.2f}% 主力{row.net_flow_yi:+.2f}亿({row.flow_source}){leader}")
        quote_service.publish_quote_context(
            page="板块资金",
            signal_extra="\n".join(extra_lines),
        )

    def _request_ai(self) -> None:
        snap = self._last_snapshot
        if snap is None or not snap.rows:
            page_notify(self._page, "请先刷新板块数据", level="warning")
            return
        if self._event_engine is None:
            return
        kind_label = "概念" if snap.sector_kind == "concept" else "行业"
        mode_note = {
            "intraday": "盘中为行情聚合估算",
            "official_dc": "东财官方日终板块资金",
            "official_ths": "同花顺官方日终概念资金",
        }.get(snap.data_mode, "")
        lines = [
            f"请解读当前{kind_label}板块资金结构：哪些板块资金净流入/流出突出，与涨幅是否一致，短线需关注什么。",
            f"数据口径：{mode_note}，请说明不确定性。",
        ]
        rotation = self._last_rotation
        if rotation and rotation.rows and rotation.sector_kind == snap.sector_kind:
            lines.append("近15日资金轮动：")
            lines.extend(format_rotation_ai_lines(rotation, limit=10))
        outlook = self._last_outlook
        if outlook and outlook.continuation.rows and outlook.continuation.sector_kind == snap.sector_kind:
            lines.append("未来3日资金延续展望（统计情景，非预测）：")
            lines.extend(format_continuation_ai_lines(outlook.continuation, limit=10))
        lines.append("当日板块快照：")
        for row in snap.rows[:12]:
            leader = f"，龙头 {row.leader_stock}" if row.leader_stock else ""
            lines.append(f"- {row.name}：强度{row.strength:.1f}，涨幅{row.change_pct:+.2f}%，主力净额{row.net_flow_yi:+.2f}亿（{row.flow_source}）{leader}")
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt="\n".join(lines), source_page="板块资金"),
            )
        )
