"""单标的下载、补全、重下与删除。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.runtime import format_vt_symbol_cn
from vnpy_ashare.data.minute_periods import DEFAULT_MINUTE_DOWNLOAD_MONTHS
from vnpy_ashare.services.bar import delete_scope_bars
from vnpy_ashare.ui.quotes.chart.tab_indices import MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.controllers.local_data.base import LocalDataControllerBase
from vnpy_ashare.ui.quotes.controllers.local_data.watchlist_hooks import refresh_watchlist_strategy_panels
from vnpy_ashare.ui.quotes.page.run_log import begin_run_log, complete_run_log, fail_run_log
from vnpy_ashare.ui.quotes.workers.quotes_workers import DownloadWorker, MinuteDownloadWorker
from vnpy_common.ui.feedback import confirm_action

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class LocalDataDownloadMixin(LocalDataControllerBase):
    def download_selected(self) -> None:
        page = self._p
        if page.config.show_chart_tabs and page.chart_panel is not None and page.chart_panel.current_tab_index() == MINUTE_TAB_INDEX:
            self.run_minute_download(mode="full")
            return
        self.run_download(mode="full", action_label="下载")

    def fill_selected(self) -> None:
        page = self._p
        if page.config.use_local_table and not self.is_daily_scope():
            self.run_minute_download(mode="incremental", action_label="补全")
            return
        self.run_download(mode="incremental", action_label="补全")

    def redownload_selected(self) -> None:
        page = self._p
        if page.config.use_local_table and not self.is_daily_scope():
            self.run_minute_download(mode="full", action_label="重新下载")
            return
        self.run_download(mode="full", action_label="重新下载")

    def delete_selected(self) -> None:
        page = self._p
        if not page.config.show_delete_button or not page.config.use_local_table:
            return
        if not page.current_item:
            return
        if page._thread_active(page._download_worker) or self._batch_worker_active():
            return

        item = page.current_item
        key = (item.symbol, item.exchange)
        if key not in page.bar_meta:
            return

        scope_label = self.scope_label()
        label = format_vt_symbol_cn(item.symbol, item.exchange)
        display = f"{item.name}（{label}）" if item.name else label
        if not confirm_action(
            page,
            "删除本地数据",
            f"确定删除 {display} 的本地{scope_label}？\n\n此操作不可恢复。",
            confirm_text="删除",
            destructive=True,
        ):
            return

        begin_run_log(page, f"删除本地{scope_label} · {display}")
        if not delete_scope_bars(item.symbol, item.exchange, page._local_scope):
            message = f"{label} 无本地{scope_label}可删除"
            page.status_label.setText(message)
            fail_run_log(page, message)
            return

        page._selected_gap_result = None
        deleted_key = (item.symbol, item.exchange)
        self.reset_meta_cache()
        if page.current_item is not None and (page.current_item.symbol, page.current_item.exchange) == deleted_key:
            page.current_item = None
            self.clear_chart()
            self.set_chart_hint(None)
        page._local_total = max(page._local_total - 1, 0)
        page.load_stock_list()
        page._update_action_buttons()
        summary = f"已删除 {display} 的本地{scope_label}"
        page.status_label.setText(summary)
        page._toast.success(summary)
        complete_run_log(page, summary)

    @staticmethod
    def _download_primary(page: QuotesPage, action_label: str) -> tuple[QtWidgets.QPushButton, str, object]:
        if action_label == "补全":
            return page.fill_button, "补全", page.fill_selected
        if action_label == "重新下载":
            return page.redownload_button, "重新下载", page.redownload_selected
        return page.download_button, page.download_button.text(), page.download_selected

    def run_minute_download(self, *, mode: Literal["full", "incremental"] = "full", action_label: str = "下载") -> None:
        page = self._p
        if page._task_guard.active or not page.current_item or page._thread_active(page._download_worker):
            return
        if page.chart_panel is None and not page.config.use_local_table:
            return

        item = page.current_item
        label = format_vt_symbol_cn(item.symbol, item.exchange)
        if page.config.use_local_table:
            period = page._local_scope
            period_label = self.scope_label()
        elif page.chart_panel is not None:
            period = page.chart_panel.current_period()
            period_label = page.chart_panel.current_period_label()
        else:
            return

        if mode == "incremental":
            status_text = f"{action_label} {label} {period_label}…"
        else:
            status_text = f"{action_label} {label} {period_label}（近{DEFAULT_MINUTE_DOWNLOAD_MONTHS}个月）…"
        primary, primary_text, primary_handler = self._download_primary(page, action_label)
        page._begin_cancellable_task(
            status_text,
            worker_attr="_download_worker",
            primary=primary,
            primary_text=primary_text,
            primary_handler=primary_handler,
        )
        page.status_label.setText(status_text)
        if page.config.show_run_output_panel:
            begin_run_log(page, f"{action_label} {label} {period_label}")

        worker = MinuteDownloadWorker(item, period=period, mode=mode)
        page._download_worker = worker
        if page.config.show_run_output_panel:
            self._connect_worker_log(worker)

        def on_finished(count: int) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            if page._finish_cancellable_task(cancelled_message=f"{action_label}已取消"):
                if page.config.show_run_output_panel:
                    fail_run_log(page, "已取消")
                return
            if page.config.use_local_table:
                self.refresh_meta()
                page.apply_filter()
            if page.chart_panel is not None:
                page.chart_panel.refresh_active()
            elif page.current_item is not None:
                page.show_kline(page.current_item)
            if mode == "incremental" and count == 0:
                summary = f"{label} 已是最新，无新增 K 线"
            elif action_label == "下载":
                summary = f"{label} 已下载 {count} 根{period_label}"
            else:
                summary = f"{label} {action_label}完成，新增 {count} 根"
            page.status_label.setText(summary)
            page._toast.success(summary)
            if page.config.show_run_output_panel:
                complete_run_log(page, summary)

        def on_failed(msg: str) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            if page._finish_cancellable_task(cancelled_message=f"{action_label}已取消"):
                if page.config.show_run_output_panel:
                    fail_run_log(page, "已取消")
                return
            page.status_label.setText(f"{action_label}分K失败: {msg}")
            page._toast.error(msg)
            if page.config.show_run_output_panel:
                fail_run_log(page, msg)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def run_download(self, *, mode: Literal["full", "incremental"], action_label: str) -> None:
        page = self._p
        if page._task_guard.active or not page.current_item or page._thread_active(page._download_worker):
            return

        item = page.current_item
        label = format_vt_symbol_cn(item.symbol, item.exchange)
        status_text = f"{action_label} {label} 日K…"
        primary, primary_text, primary_handler = self._download_primary(page, action_label)
        page._begin_cancellable_task(
            status_text,
            worker_attr="_download_worker",
            primary=primary,
            primary_text=primary_text,
            primary_handler=primary_handler,
        )
        page.status_label.setText(status_text)
        if page.config.show_run_output_panel:
            begin_run_log(page, f"{action_label} {label} 日K")

        worker = DownloadWorker(item, mode=mode)
        page._download_worker = worker
        if page.config.show_run_output_panel:
            self._connect_worker_log(worker)

        def on_finished(count: int) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            if page._finish_cancellable_task(cancelled_message=f"{action_label}已取消"):
                if page.config.show_run_output_panel:
                    fail_run_log(page, "已取消")
                return
            self.refresh_meta()
            page.apply_filter()
            page.show_kline(item)
            if page.config.show_fill_button and self.is_daily_scope():
                self.check_bar_gaps(item)
            if mode == "incremental" and count == 0:
                summary = f"{label} 已是最新，无新增 K 线"
            elif action_label == "下载":
                summary = f"{label} 已下载 {count} 根日K"
            else:
                summary = f"{label} {action_label}完成，新增 {count} 根日K"
            page.status_label.setText(summary)
            page._toast.success(summary)
            if page.config.show_run_output_panel:
                complete_run_log(page, summary)
            refresh_watchlist_strategy_panels(page, [item.vt_symbol])
            if page.config.show_watchlist_multiview:
                page._multiview.on_bars_updated([item.vt_symbol])

        def on_failed(msg: str) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            if page._finish_cancellable_task(cancelled_message=f"{action_label}已取消"):
                if page.config.show_run_output_panel:
                    fail_run_log(page, "已取消")
                return
            page.status_label.setText(f"{action_label}失败: {msg}")
            page._toast.error(msg)
            if page.config.show_run_output_panel:
                fail_run_log(page, msg)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()
