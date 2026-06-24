"""快照加载、板块选中与成分龙头。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import (
    SectorConstituentRow,
    SectorFlowHistoryPoint,
    SectorFlowOutlookRow,
    SectorFlowRotationRow,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.ui.sector_flow.controller.base import TAB_OUTLOOK, TAB_OVERVIEW, TAB_ROTATION, SectorFlowControllerBase
from vnpy_ashare.ui.sector_flow.leaders_worker import SectorLeadersLoadWorker
from vnpy_ashare.ui.sector_flow.outlook_detail_dialog import SectorFlowOutlookDetailDialog
from vnpy_ashare.ui.sector_flow.rotation_detail_dialog import SectorFlowRotationDetailDialog
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active


class SectorFlowSnapshotMixin(SectorFlowControllerBase):
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
        if self._panel.active_tab == TAB_OVERVIEW:
            first_row = None
            if snapshot.inflow_rows:
                first_row = snapshot.inflow_rows[0]
            elif snapshot.outflow_rows:
                first_row = snapshot.outflow_rows[0]
            if first_row is not None:
                self._load_sector_leaders(first_row)
            return
        if self._panel.active_tab == TAB_ROTATION:
            self._load_rotation(snapshot)
            return
        if self._panel.active_tab == TAB_OUTLOOK:
            self._load_outlook(snapshot)
            return
        first_row = self._panel.table.selected_sector_row()
        if first_row is None and snapshot.inflow_rows:
            self._panel.table.selectRow(0)
            first_row = self._panel.table.selected_sector_row()
        if first_row is not None:
            self._load_sector_leaders(first_row)

    def _on_sector_selected(self, sector: SectorFlowRow) -> None:
        if self._panel.active_tab in {TAB_ROTATION, TAB_OUTLOOK}:
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
