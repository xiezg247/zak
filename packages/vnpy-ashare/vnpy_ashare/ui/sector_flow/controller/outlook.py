"""未来 3 日展望与成分策略批量扫描。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import SectorFlowOutlookBundle, SectorFlowOutlookRow, SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import outlook_strategy_label, save_sector_flow_outlook_strategy_class
from vnpy_ashare.services.sector_flow_outlook_strategy import classify_sector_resonance
from vnpy_ashare.ui.sector_flow.controller.base import TAB_OUTLOOK, SectorFlowControllerBase
from vnpy_ashare.ui.sector_flow.outlook_batch import coerce_sector_flow_rows, format_batch_scan_summary, prepare_batch_sector_scans
from vnpy_ashare.ui.sector_flow.outlook_worker import SectorFlowOutlookLoadWorker
from vnpy_ashare.ui.sector_flow.sector_strategy_worker import SectorFlowSectorStrategyWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active


class SectorFlowOutlookMixin(SectorFlowControllerBase):
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
        if self._panel.active_tab != TAB_OUTLOOK:
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
        if self._panel.active_tab != TAB_OUTLOOK:
            self._panel.select_view_tab(TAB_OUTLOOK, emit=True)
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
