"""批量补全、断层修复与工具栏按钮状态。"""

from __future__ import annotations

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.data.bar_health import BarHealthStatus, format_gap_ranges, list_status
from vnpy_ashare.jobs.bars.local_fill import (
    BatchFillProgress,
    BatchFillResult,
    BatchGapFillProgress,
    BatchGapFillResult,
    count_scannable_daily_items,
    count_stale_daily_items,
    select_stale_daily_items,
)
from vnpy_ashare.ui.quotes.controllers.local_data.base import LocalDataControllerBase
from vnpy_ashare.ui.quotes.controllers.local_data.watchlist_hooks import (
    position_vt_symbols,
    refresh_watchlist_strategy_panels,
)
from vnpy_ashare.ui.quotes.page.run_log import append_run_log, begin_run_log, complete_run_log, fail_run_log
from vnpy_ashare.ui.quotes.workers.quotes_workers import BatchFillWorker, BatchGapFillWorker
from vnpy_common.ui.feedback import confirm_action


class LocalDataBatchOpsMixin(LocalDataControllerBase):
    def update_batch_toolbar_buttons(self) -> None:
        self.update_batch_fill_button()
        self.update_batch_gap_fill_button()
        self.update_gap_fill_button()

    def update_batch_fill_button(self) -> None:
        page = self._p
        button = getattr(page, "batch_fill_button", None)
        if button is None or not page.config.show_batch_fill_button:
            return
        if not page.config.use_local_table or not self.is_daily_scope():
            button.setEnabled(False)
            return
        if page._thread_active(getattr(page, "_batch_fill_worker", None)):
            button.setEnabled(False)
            return
        stale_count = count_stale_daily_items(page.all_stocks, page.bar_meta)
        button.setEnabled(stale_count > 0)
        scope = "当前页" if page.config.use_local_pagination else "列表"
        button.setToolTip(f"对{scope} {stale_count} 只过期标的增量补全日 K 到最新交易日" if stale_count else f"当前{scope}无过期日 K")

    def update_batch_gap_fill_button(self) -> None:
        page = self._p
        button = getattr(page, "batch_gap_fill_button", None)
        if button is None or not page.config.show_batch_gap_fill_button:
            return
        if not page.config.use_local_table or not self.is_daily_scope():
            button.setEnabled(False)
            return
        if page._thread_active(getattr(page, "_batch_gap_fill_worker", None)):
            button.setEnabled(False)
            return
        if page._thread_active(getattr(page, "_batch_fill_worker", None)):
            button.setEnabled(False)
            return
        scannable = count_scannable_daily_items(page.all_stocks, page.bar_meta)
        button.setEnabled(scannable > 0)
        button.setToolTip(f"扫描并修复列表内 {scannable} 只日 K 的内部断层" if scannable else "当前列表无本地日 K")

    def update_gap_fill_button(self) -> None:
        page = self._p
        button = getattr(page, "gap_fill_button", None)
        if button is None or not page.config.show_batch_gap_fill_button:
            return
        if not page.config.use_local_table or not self.is_daily_scope():
            button.setEnabled(False)
            return
        if self._batch_worker_active():
            button.setEnabled(False)
            return
        item = page.current_item
        if item is None:
            button.setEnabled(False)
            return
        key = (item.symbol, item.exchange)
        meta = page.bar_meta.get(key)
        if meta is None:
            button.setEnabled(False)
            return
        status = page.bar_list_status.get(key, list_status(meta))
        has_gaps = status == BarHealthStatus.GAPS
        button.setEnabled(has_gaps)
        if has_gaps and page._selected_gap_result is not None and page._selected_gap_result.gaps:
            gap_text = format_gap_ranges(page._selected_gap_result.gaps)
            button.setToolTip(f"修复 {len(page._selected_gap_result.gaps)} 处断层：{gap_text}")
        elif has_gaps:
            button.setToolTip("扫描并修复当前标的日 K 内部断层")
        else:
            button.setToolTip("当前标的无内部断层")

    def _batch_worker_active(self) -> bool:
        page = self._p
        return page._thread_active(getattr(page, "_batch_fill_worker", None)) or page._thread_active(getattr(page, "_batch_gap_fill_worker", None))

    def batch_fill_stale(self) -> None:
        page = self._p
        if not page.config.show_batch_fill_button or not self.is_daily_scope():
            return
        if page._task_guard.active:
            return
        if page._thread_active(page._download_worker) or self._batch_worker_active():
            return

        items = select_stale_daily_items(page.all_stocks, page.bar_meta)
        if not items:
            self.update_batch_toolbar_buttons()
            return

        stale_count = count_stale_daily_items(page.all_stocks, page.bar_meta)
        if not confirm_action(
            page,
            "批量补全过期日 K",
            f"将为 {stale_count} 只过期标的增量补全日 K 到最新交易日，可能耗时较长。\n\n是否继续？",
            confirm_text="开始补全",
        ):
            return

        page._begin_cancellable_task(
            f"批量补全过期日 K（0/{len(items)}）…",
            worker_attr="_batch_fill_worker",
            primary=page.batch_fill_button,
            primary_text="批量补全过期",
            primary_handler=page.batch_fill_stale,
        )
        self.update_batch_toolbar_buttons()
        begin_run_log(page, f"批量补全过期日 K · {len(items)} 只")

        worker = BatchFillWorker(items, dict(page.bar_meta))
        page._batch_fill_worker = worker

        def on_progress(progress: object) -> None:
            if not isinstance(progress, BatchFillProgress):
                return
            line = f"({progress.current}/{progress.total}) {progress.label}"
            page.status_label.setText(f"批量补全 {line}...")
            page._task_guard.update_message(f"批量补全 {line}…")
            append_run_log(page, line)

        def on_finished(result: object) -> None:
            if page._batch_fill_worker is worker:
                page._batch_fill_worker = None
            if page._finish_cancellable_task(cancelled_message="批量补全已取消"):
                fail_run_log(page, "已取消")
                self.update_batch_toolbar_buttons()
                return
            self.refresh_meta()
            page.apply_filter()
            if page.current_item is not None and self.is_daily_scope():
                page.show_kline(page.current_item)
                self.check_bar_gaps(page.current_item)
            self.update_batch_toolbar_buttons()
            if isinstance(result, BatchFillResult):
                page.status_label.setText(result.message)
                page._toast.success(result.message)
                detail = None
                if result.failed:
                    preview = "、".join(result.failed[:8])
                    suffix = "…" if len(result.failed) > 8 else ""
                    detail = f"失败 {len(result.failed)} 只：{preview}{suffix}"
                complete_run_log(page, result.message, detail=detail)
            if isinstance(result, BatchFillResult) and (result.success or result.bars_added):
                refresh_watchlist_strategy_panels(page, [item.vt_symbol for item in items])

        def on_failed(msg: str) -> None:
            if page._batch_fill_worker is worker:
                page._batch_fill_worker = None
            if page._finish_cancellable_task(cancelled_message="批量补全已取消"):
                fail_run_log(page, "已取消")
                self.update_batch_toolbar_buttons()
                return
            self.update_batch_toolbar_buttons()
            page.status_label.setText(f"批量补全失败: {msg}")
            page._toast.error(msg)
            fail_run_log(page, msg)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def batch_fill_gaps(self) -> None:
        page = self._p
        if not page.config.show_batch_gap_fill_button or not self.is_daily_scope():
            return
        if page._task_guard.active:
            return
        if page._thread_active(page._download_worker) or self._batch_worker_active():
            return

        scannable = count_scannable_daily_items(page.all_stocks, page.bar_meta)
        if scannable == 0:
            self.update_batch_toolbar_buttons()
            return

        if not confirm_action(
            page,
            "批量修复断层",
            f"将扫描列表内 {scannable} 只日 K 的内部断层并下载缺失区间，可能耗时较长。\n\n是否继续？",
            confirm_text="开始修复",
        ):
            return

        page._begin_cancellable_task(
            f"扫描断层（0/{scannable}）…",
            worker_attr="_batch_gap_fill_worker",
            primary=page.batch_gap_fill_button,
            primary_text="批量修复断层",
            primary_handler=page.batch_fill_gaps,
        )
        self.update_batch_toolbar_buttons()
        begin_run_log(page, f"批量修复断层 · 扫描 {scannable} 只")

        worker = BatchGapFillWorker(page.all_stocks, dict(page.bar_meta))
        page._batch_gap_fill_worker = worker

        def on_progress(progress: object) -> None:
            if not isinstance(progress, BatchGapFillProgress):
                return
            phase_label = "扫描断层" if progress.phase == "scan" else "修复断层"
            line = f"{phase_label} ({progress.current}/{progress.total}) {progress.label}"
            page.status_label.setText(f"{line}...")
            page._task_guard.update_message(f"{line}…")
            append_run_log(page, line)

        def on_finished(result: object) -> None:
            if page._batch_gap_fill_worker is worker:
                page._batch_gap_fill_worker = None
            if page._finish_cancellable_task(cancelled_message="批量修复已取消"):
                fail_run_log(page, "已取消")
                self.update_batch_toolbar_buttons()
                return
            self.refresh_meta()
            page.apply_filter()
            if page.current_item is not None and self.is_daily_scope():
                page.show_kline(page.current_item)
                self.check_bar_gaps(page.current_item)
            self.update_batch_toolbar_buttons()
            if isinstance(result, BatchGapFillResult):
                page.status_label.setText(result.message)
                page._toast.success(result.message)
                detail = None
                if result.failed:
                    preview = "、".join(result.failed[:8])
                    suffix = "…" if len(result.failed) > 8 else ""
                    detail = f"失败 {len(result.failed)} 只：{preview}{suffix}"
                complete_run_log(page, result.message, detail=detail)
            if isinstance(result, BatchGapFillResult) and result.bars_added:
                panel = getattr(page, "signal_panel", None)
                symbols: list[str] = []
                if panel is not None:
                    symbols.extend(panel.symbols)
                symbols.extend(position_vt_symbols(page))
                if symbols:
                    refresh_watchlist_strategy_panels(page, list(dict.fromkeys(symbols)))

        def on_failed(msg: str) -> None:
            if page._batch_gap_fill_worker is worker:
                page._batch_gap_fill_worker = None
            if page._finish_cancellable_task(cancelled_message="批量修复已取消"):
                fail_run_log(page, "已取消")
                self.update_batch_toolbar_buttons()
                return
            self.update_batch_toolbar_buttons()
            page.status_label.setText(f"批量修复断层失败: {msg}")
            page._toast.error(msg)
            fail_run_log(page, msg)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def fill_selected_gaps(self) -> None:
        page = self._p
        if not page.config.show_batch_gap_fill_button or not self.is_daily_scope():
            return
        if page._task_guard.active:
            return
        if page._thread_active(page._download_worker) or self._batch_worker_active():
            return
        if not page.current_item:
            return

        item = page.current_item
        key = (item.symbol, item.exchange)
        meta = page.bar_meta.get(key)
        if meta is None:
            page._toast.warning("该标的无本地日 K")
            return

        label = format_vt_symbol_cn(item.symbol, item.exchange)
        display = f"{item.name}（{label}）" if item.name else label
        gap_result = page._selected_gap_result
        if gap_result is not None and gap_result.status == BarHealthStatus.GAPS and gap_result.gaps:
            gap_text = format_gap_ranges(gap_result.gaps)
            message = f"将为 {display} 修复 {len(gap_result.gaps)} 处断层：\n{gap_text}\n\n是否继续？"
        else:
            message = f"将扫描 {display} 的日 K 并修复内部断层。\n\n是否继续？"

        if not confirm_action(page, "修复断层", message, confirm_text="开始修复"):
            return

        page._begin_cancellable_task(
            f"扫描断层 · {label}…",
            worker_attr="_batch_gap_fill_worker",
            primary=page.gap_fill_button,
            primary_text="修复断层",
            primary_handler=page.fill_selected_gaps,
        )
        self.update_batch_toolbar_buttons()
        begin_run_log(page, f"修复断层 · {display}")

        worker = BatchGapFillWorker([item], {key: meta})
        page._batch_gap_fill_worker = worker

        def on_progress(progress: object) -> None:
            if not isinstance(progress, BatchGapFillProgress):
                return
            phase_label = "扫描断层" if progress.phase == "scan" else "修复断层"
            line = f"{phase_label} · {label} ({progress.current}/{progress.total})"
            page.status_label.setText(f"{line}…")
            page._task_guard.update_message(f"{line}…")
            append_run_log(page, line)

        def on_finished(result: object) -> None:
            if page._batch_gap_fill_worker is worker:
                page._batch_gap_fill_worker = None
            if page._finish_cancellable_task(cancelled_message="修复断层已取消"):
                fail_run_log(page, "已取消")
                self.update_batch_toolbar_buttons()
                return
            self.refresh_meta()
            page.apply_filter()
            if page.current_item is not None and self.is_daily_scope():
                page.show_kline(page.current_item)
                self.check_bar_gaps(page.current_item)
            self.update_batch_toolbar_buttons()
            if isinstance(result, BatchGapFillResult):
                page.status_label.setText(result.message)
                page._toast.success(result.message)
                detail = None
                if result.failed:
                    preview = "、".join(result.failed[:8])
                    suffix = "…" if len(result.failed) > 8 else ""
                    detail = f"失败 {len(result.failed)} 只：{preview}{suffix}"
                complete_run_log(page, result.message, detail=detail)
            if isinstance(result, BatchGapFillResult) and result.bars_added:
                panel = getattr(page, "signal_panel", None)
                symbols: list[str] = []
                if panel is not None:
                    symbols.extend(panel.symbols)
                symbols.extend(position_vt_symbols(page))
                if symbols:
                    refresh_watchlist_strategy_panels(page, list(dict.fromkeys(symbols)))

        def on_failed(msg: str) -> None:
            if page._batch_gap_fill_worker is worker:
                page._batch_gap_fill_worker = None
            if page._finish_cancellable_task(cancelled_message="修复断层已取消"):
                fail_run_log(page, "已取消")
                self.update_batch_toolbar_buttons()
                return
            self.update_batch_toolbar_buttons()
            page.status_label.setText(f"修复断层失败: {msg}")
            page._toast.error(msg)
            fail_run_log(page, msg)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()
