"""本地 K 线元数据、下载与图表加载。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.bar_health import (
    BarGapResult,
    BarHealthStatus,
    BarMeta,
    format_gap_ranges,
    format_meta_datetime,
    list_status,
)
from vnpy_ashare.calendar import last_trading_day
from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.minute_periods import DEFAULT_MINUTE_DOWNLOAD_MONTHS, is_daily_scope, scope_display
from vnpy_ashare.models import StockItem
from vnpy_ashare.ui.chart_panel import MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.workers import (
    BarGapCheckWorker,
    BarsLoadWorker,
    BatchFillWorker,
    BatchGapFillWorker,
    DownloadWorker,
    LoadedBars,
    MinuteDownloadWorker,
    ScopeBarsLoadWorker,
)
from vnpy_ashare.ui.quotes_chart import AshareChartWidget, prepare_chart_bars

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes_page import QuotesPage


def should_apply_loaded_bars(
    *,
    generation: int,
    current_generation: int,
    request_id: int,
    current_request_id: int,
    target_key: tuple[str, Exchange],
    current_key: tuple[str, Exchange] | None,
    target_scope: str,
    current_scope: str,
    loaded_key: tuple[str, Exchange] | None = None,
) -> bool:
    """K 线回调是否应写入图表（标的、周期、generation 须一致）。"""
    if generation != current_generation:
        return False
    if request_id != current_request_id:
        return False
    if current_key is None or current_key != target_key:
        return False
    if target_scope != current_scope:
        return False
    if loaded_key is not None and loaded_key != target_key:
        return False
    return True


class LocalDataController:
    """本地 K 线元数据、下载、缺口检查与图表加载。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def is_daily_scope(self) -> bool:
        page = self._page
        return not page.config.use_local_table or is_daily_scope(page._local_scope)

    def scope_label(self) -> str:
        return scope_display(self._page._local_scope)

    def refresh_meta(self) -> None:
        page = self._page
        page.downloaded_keys = set()
        page.bar_meta = {}
        page.bar_list_status = {}
        bar_svc = page._get_bar_service()
        rows = bar_svc.iter_overviews(page._local_scope) if bar_svc else self._fallback_overviews(page._local_scope)
        for row in rows:
            key = (row.symbol, row.exchange)
            meta = BarMeta(start=row.start, end=row.end, count=row.count)
            page.downloaded_keys.add(key)
            page.bar_meta[key] = meta
            page.bar_list_status[key] = list_status(meta)

    @staticmethod
    def _fallback_overviews(scope: str):
        """BarService 不可用时经 bar_access 枚举本地 K 线概览。"""
        from vnpy_ashare.bar_access import iter_bar_overviews

        return iter_bar_overviews(scope=scope)

    def update_batch_toolbar_buttons(self) -> None:
        self.update_batch_fill_button()
        self.update_batch_gap_fill_button()

    def update_batch_fill_button(self) -> None:
        page = self._page
        button = getattr(page, "batch_fill_button", None)
        if button is None or not page.config.show_batch_fill_button:
            return
        visible = page.config.use_local_table and self.is_daily_scope()
        button.setVisible(visible)
        if not visible:
            button.setEnabled(False)
            return
        if page._thread_active(getattr(page, "_batch_fill_worker", None)):
            button.setEnabled(False)
            return
        from vnpy_ashare.jobs.local_fill import count_stale_daily_items

        stale_count = count_stale_daily_items(page.all_stocks, page.bar_meta)
        button.setEnabled(stale_count > 0)
        button.setToolTip(f"对 {stale_count} 只过期标的增量补全日 K 到最新交易日" if stale_count else "当前列表无过期日 K")

    def update_batch_gap_fill_button(self) -> None:
        page = self._page
        button = getattr(page, "batch_gap_fill_button", None)
        if button is None or not page.config.show_batch_gap_fill_button:
            return
        visible = page.config.use_local_table and self.is_daily_scope()
        button.setVisible(visible)
        if not visible:
            button.setEnabled(False)
            return
        if page._thread_active(getattr(page, "_batch_gap_fill_worker", None)):
            button.setEnabled(False)
            return
        if page._thread_active(getattr(page, "_batch_fill_worker", None)):
            button.setEnabled(False)
            return
        from vnpy_ashare.jobs.local_fill import count_scannable_daily_items

        scannable = count_scannable_daily_items(page.all_stocks, page.bar_meta)
        button.setEnabled(scannable > 0)
        button.setToolTip(f"扫描并修复列表内 {scannable} 只日 K 的内部断层" if scannable else "当前列表无本地日 K")

    def _batch_worker_active(self) -> bool:
        page = self._page
        return page._thread_active(getattr(page, "_batch_fill_worker", None)) or page._thread_active(getattr(page, "_batch_gap_fill_worker", None))

    def batch_fill_stale(self) -> None:
        page = self._page
        if not page.config.show_batch_fill_button or not self.is_daily_scope():
            return
        if page._thread_active(page._download_worker) or self._batch_worker_active():
            return

        from vnpy_ashare.jobs.local_fill import count_stale_daily_items, select_stale_daily_items

        items = select_stale_daily_items(page.all_stocks, page.bar_meta)
        if not items:
            QtWidgets.QMessageBox.information(page, "批量补全", "当前没有需要补全的过期日 K")
            self.update_batch_toolbar_buttons()
            return

        stale_count = count_stale_daily_items(page.all_stocks, page.bar_meta)
        reply = QtWidgets.QMessageBox.question(
            page,
            "批量补全过期日 K",
            f"将为 {stale_count} 只过期标的增量补全日 K 到最新交易日，可能耗时较长。\n\n是否继续？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        page._set_busy(True)
        self.update_batch_toolbar_buttons()
        page.status_label.setText(f"批量补全过期日 K（0/{len(items)}）...")

        worker = BatchFillWorker(items, dict(page.bar_meta))
        page._batch_fill_worker = worker

        def on_progress(progress: object) -> None:
            from vnpy_ashare.jobs.local_fill import BatchFillProgress

            if not isinstance(progress, BatchFillProgress):
                return
            page.status_label.setText(f"批量补全 ({progress.current}/{progress.total}) {progress.label}...")

        def on_finished(result: object) -> None:
            if page._batch_fill_worker is worker:
                page._batch_fill_worker = None
            page._set_busy(False)
            self.refresh_meta()
            page.apply_filter()
            if page.current_item is not None and self.is_daily_scope():
                page.show_kline(page.current_item)
                self.check_bar_gaps(page.current_item)
            self.update_batch_toolbar_buttons()
            from vnpy_ashare.jobs.local_fill import BatchFillResult

            if isinstance(result, BatchFillResult):
                page.status_label.setText(result.message)

        def on_failed(msg: str) -> None:
            if page._batch_fill_worker is worker:
                page._batch_fill_worker = None
            page._set_busy(False)
            self.update_batch_toolbar_buttons()
            page.status_label.setText(f"批量补全失败: {msg}")

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def batch_fill_gaps(self) -> None:
        page = self._page
        if not page.config.show_batch_gap_fill_button or not self.is_daily_scope():
            return
        if page._thread_active(page._download_worker) or self._batch_worker_active():
            return

        from vnpy_ashare.jobs.local_fill import count_scannable_daily_items

        scannable = count_scannable_daily_items(page.all_stocks, page.bar_meta)
        if scannable == 0:
            QtWidgets.QMessageBox.information(page, "批量修复断层", "当前列表无本地日 K 可扫描")
            self.update_batch_toolbar_buttons()
            return

        reply = QtWidgets.QMessageBox.question(
            page,
            "批量修复断层",
            f"将扫描列表内 {scannable} 只日 K 的内部断层并下载缺失区间，可能耗时较长。\n\n是否继续？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        page._set_busy(True)
        self.update_batch_toolbar_buttons()
        page.status_label.setText(f"扫描断层（0/{scannable}）...")

        worker = BatchGapFillWorker(page.all_stocks, dict(page.bar_meta))
        page._batch_gap_fill_worker = worker

        def on_progress(progress: object) -> None:
            from vnpy_ashare.jobs.local_fill import BatchGapFillProgress

            if not isinstance(progress, BatchGapFillProgress):
                return
            phase_label = "扫描断层" if progress.phase == "scan" else "修复断层"
            page.status_label.setText(f"{phase_label} ({progress.current}/{progress.total}) {progress.label}...")

        def on_finished(result: object) -> None:
            if page._batch_gap_fill_worker is worker:
                page._batch_gap_fill_worker = None
            page._set_busy(False)
            self.refresh_meta()
            page.apply_filter()
            if page.current_item is not None and self.is_daily_scope():
                page.show_kline(page.current_item)
                self.check_bar_gaps(page.current_item)
            self.update_batch_toolbar_buttons()
            from vnpy_ashare.jobs.local_fill import BatchGapFillResult

            if isinstance(result, BatchGapFillResult):
                page.status_label.setText(result.message)

        def on_failed(msg: str) -> None:
            if page._batch_gap_fill_worker is worker:
                page._batch_gap_fill_worker = None
            page._set_busy(False)
            self.update_batch_toolbar_buttons()
            page.status_label.setText(f"批量修复断层失败: {msg}")

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def on_period_changed(self) -> None:
        page = self._page
        if not page.config.use_local_table:
            return
        value = page.local_period_combo.currentData()
        if not isinstance(value, str) or value == page._local_scope:
            return
        page._local_scope = value
        page._selected_gap_result = None
        self.refresh_meta()
        self.update_batch_toolbar_buttons()
        page.load_stock_list()
        if page.current_item is not None:
            page.show_kline(page.current_item)
            if self.is_daily_scope():
                self.check_bar_gaps(page.current_item)
            elif page.chart_hint is not None:
                self.update_coverage_hint(page.current_item)

    def set_chart_hint(self, text: str | None) -> None:
        page = self._page
        if page.chart_hint is None:
            return
        if text:
            page.chart_hint.setText(text)
            page.chart_hint.show()
        else:
            page.chart_hint.hide()

    def update_coverage_hint(self, item: StockItem) -> None:
        page = self._page
        if not page.config.show_fill_button or page.chart_hint is None:
            return
        key = (item.symbol, item.exchange)
        meta = page.bar_meta.get(key)
        scope_label = self.scope_label()
        if meta is None:
            self.set_chart_hint(f"暂无本地{scope_label}")
            return

        minute = not self.is_daily_scope()
        lines = [f"{scope_label}：{format_meta_datetime(meta.start, minute=minute)} ~ {format_meta_datetime(meta.end, minute=minute)}，共 {meta.count} 根"]
        status = page.bar_list_status.get(key, list_status(meta))
        if status == BarHealthStatus.STALE:
            latest = last_trading_day()
            lines.append(f"⚠️ 数据过期，最新应为 {latest.isoformat()}，请点击「补全到最新」")
        elif self.is_daily_scope() and status == BarHealthStatus.GAPS and page._selected_gap_result is not None:
            gap_text = format_gap_ranges(page._selected_gap_result.gaps)
            lines.append(f"🔴 发现 {len(page._selected_gap_result.gaps)} 处断层：{gap_text}")
        self.set_chart_hint("\n".join(lines))

    def check_bar_gaps(self, item: StockItem) -> None:
        page = self._page
        if not page.config.show_fill_button or not self.is_daily_scope():
            return
        key = (item.symbol, item.exchange)
        meta = page.bar_meta.get(key)
        if meta is None:
            page._selected_gap_result = None
            self.update_coverage_hint(item)
            return

        if page._thread_active(page._gap_worker):
            page._wait_worker_release("_gap_worker")

        page._gap_generation += 1
        generation = page._gap_generation
        self.set_chart_hint("正在检查数据完整性...")

        worker = BarGapCheckWorker(item, meta)
        page._gap_worker = worker

        def on_finished(result: object) -> None:
            if generation != page._gap_generation:
                return
            if page._gap_worker is worker:
                page._gap_worker = None
            if not page._active or page.current_item is None:
                return
            if (page.current_item.symbol, page.current_item.exchange) != key:
                return
            if not isinstance(result, tuple) or len(result) != 2:
                return
            result_item, gap_result = result
            if (result_item.symbol, result_item.exchange) != key:
                return
            if not isinstance(gap_result, BarGapResult):
                return

            page._selected_gap_result = gap_result
            page.bar_list_status[key] = gap_result.status
            page._refresh_row_for_item(item)
            page._update_action_buttons()
            self.update_coverage_hint(item)

        def on_failed(_msg: str) -> None:
            if generation != page._gap_generation:
                return
            if page._gap_worker is worker:
                page._gap_worker = None
            if page.current_item is None:
                return
            if (page.current_item.symbol, page.current_item.exchange) != key:
                return
            self.set_chart_hint("完整性检查失败，仍可查看已有 K 线")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def clear_chart(self) -> None:
        page = self._page
        if not page.config.show_kline:
            return
        chart = page.chart
        if isinstance(chart, AshareChartWidget):
            chart.configure_scope(minute=not self.is_daily_scope())
            chart.replace_history([])
        else:
            chart.clear_all()
            chart.move_to_right()

    def render_chart(self, bars: list[BarData]) -> None:
        page = self._page
        if not page.config.show_kline:
            return
        chart = page.chart
        minute = not self.is_daily_scope()
        if isinstance(chart, AshareChartWidget):
            chart.configure_scope(minute=minute)
            chart.replace_history(bars)
        else:
            chart.replace_history(prepare_chart_bars(bars))

    def show_kline(self, item: StockItem) -> None:
        page = self._page
        if not page.config.show_kline:
            return
        quote = page.quote_map.get(item.tickflow_symbol)
        if page.chart_panel is not None:
            page.chart_panel.load_item(item, quote=quote)
            return

        self.set_chart_hint(None)
        page._bars_generation += 1
        generation = page._bars_generation
        page._bars_request_id += 1
        request_id = page._bars_request_id
        target_key = (item.symbol, item.exchange)
        target_scope = page._local_scope

        page._wait_worker_release("_bars_worker")
        self.clear_chart()

        if self.is_daily_scope():
            worker = BarsLoadWorker(item)
        else:
            worker = ScopeBarsLoadWorker(item, scope=target_scope)
        page._bars_worker = worker

        def _should_apply(result: object) -> bool:
            if not page._active or page.current_item is None:
                return False
            current_key = (page.current_item.symbol, page.current_item.exchange)
            loaded_key = None
            if isinstance(result, LoadedBars):
                loaded_key = (result.item.symbol, result.item.exchange)
            return should_apply_loaded_bars(
                generation=generation,
                current_generation=page._bars_generation,
                request_id=request_id,
                current_request_id=page._bars_request_id,
                target_key=target_key,
                current_key=current_key,
                target_scope=target_scope,
                current_scope=page._local_scope,
                loaded_key=loaded_key,
            )

        def on_finished(result: object) -> None:
            if page._bars_worker is worker:
                page._bars_worker = None
            if not _should_apply(result):
                return
            scope_label = self.scope_label()
            if result is None:
                self.clear_chart()
                if page.config.show_fill_button:
                    self.set_chart_hint(f"暂无本地{scope_label}")
                else:
                    self.set_chart_hint(f"暂无本地{scope_label}，请点击「下载日K到本地」")
                return
            loaded: LoadedBars = result
            if loaded.bars:
                self.render_chart(loaded.bars)
                if page.config.show_fill_button:
                    self.update_coverage_hint(item)
                else:
                    self.set_chart_hint(None)
            else:
                self.clear_chart()
                if page.config.show_fill_button:
                    self.set_chart_hint(f"暂无本地{scope_label}")
                else:
                    self.set_chart_hint(f"暂无本地{scope_label}，请点击「下载日K到本地」")

        def on_failed(_msg: str) -> None:
            if page._bars_worker is worker:
                page._bars_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def download_selected(self) -> None:
        page = self._page
        if page.config.show_chart_tabs and page.chart_panel is not None and page.chart_panel.current_tab_index() == MINUTE_TAB_INDEX:
            self.run_minute_download(mode="full")
            return
        self.run_download(mode="full", action_label="下载")

    def fill_selected(self) -> None:
        page = self._page
        if page.config.use_local_table and not self.is_daily_scope():
            self.run_minute_download(mode="incremental", action_label="补全")
            return
        self.run_download(mode="incremental", action_label="补全")

    def redownload_selected(self) -> None:
        page = self._page
        if page.config.use_local_table and not self.is_daily_scope():
            self.run_minute_download(mode="full", action_label="重新下载")
            return
        self.run_download(mode="full", action_label="重新下载")

    def run_minute_download(self, *, mode: str = "full", action_label: str = "下载") -> None:
        page = self._page
        if not page.current_item or page._thread_active(page._download_worker):
            return
        if page.chart_panel is None and not page.config.use_local_table:
            return

        item = page.current_item
        if page.config.use_local_table:
            period = page._local_scope
            period_label = self.scope_label()
        else:
            period = page.chart_panel.current_period()
            period_label = page.chart_panel.current_period_label()

        page._set_busy(True)
        if mode == "incremental":
            status_text = f"{action_label} {format_vt_symbol_cn(item.symbol, item.exchange)} {period_label}..."
        else:
            status_text = f"{action_label} {format_vt_symbol_cn(item.symbol, item.exchange)} {period_label}（近{DEFAULT_MINUTE_DOWNLOAD_MONTHS}个月）..."
        page.status_label.setText(status_text)

        worker = MinuteDownloadWorker(item, period=period, mode=mode)
        page._download_worker = worker

        def on_finished(count: int) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            page._set_busy(False)
            label = format_vt_symbol_cn(item.symbol, item.exchange)
            if page.config.use_local_table:
                self.refresh_meta()
                page.apply_filter()
            if page.chart_panel is not None:
                page.chart_panel.refresh_active()
            elif page.current_item is not None:
                page.show_kline(page.current_item)
            if mode == "incremental" and count == 0:
                page.status_label.setText(f"{label} 已是最新，无新增 K 线")
            elif action_label == "下载":
                page.status_label.setText(f"{label} 已下载 {count} 根{period_label}")
            else:
                page.status_label.setText(f"{label} {action_label}完成，新增 {count} 根")

        def on_failed(msg: str) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            page._set_busy(False)
            page.status_label.setText(f"{action_label}分K失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def run_download(self, *, mode: str, action_label: str) -> None:
        page = self._page
        if not page.current_item or page._thread_active(page._download_worker):
            return

        item = page.current_item
        page._set_busy(True)
        page.status_label.setText(f"{action_label} {format_vt_symbol_cn(item.symbol, item.exchange)} 日K...")

        worker = DownloadWorker(item, mode=mode)
        page._download_worker = worker

        def on_finished(count: int) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            self.refresh_meta()
            page.apply_filter()
            page.show_kline(item)
            if page.config.show_fill_button and self.is_daily_scope():
                self.check_bar_gaps(item)
            page._set_busy(False)
            label = format_vt_symbol_cn(item.symbol, item.exchange)
            if mode == "incremental" and count == 0:
                page.status_label.setText(f"{label} 已是最新，无新增 K 线")
            elif action_label == "下载":
                page.status_label.setText(f"{label} 已下载 {count} 根日K")
            else:
                page.status_label.setText(f"{label} {action_label}完成，新增 {count} 根日K")

        def on_failed(msg: str) -> None:
            if page._download_worker is worker:
                page._download_worker = None
            page._set_busy(False)
            page.status_label.setText(f"{action_label}失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()
