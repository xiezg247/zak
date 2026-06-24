"""近 15 日板块轮动加载。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import SectorFlowRotationSnapshot, SectorFlowSnapshot
from vnpy_ashare.ui.sector_flow.controller.base import SectorFlowControllerBase
from vnpy_ashare.ui.sector_flow.rotation_worker import SectorFlowRotationLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active


class SectorFlowRotationMixin(SectorFlowControllerBase):
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

    def _on_rotation_failed(self, message: str) -> None:
        self._panel.set_loading(False)
        page_notify(self._page, f"板块轮动加载失败：{message}", level="warning")
        self._page.set_status(message)
