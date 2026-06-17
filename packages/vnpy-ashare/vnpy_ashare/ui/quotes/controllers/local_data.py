"""本地 K 线元数据、下载与图表加载。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.data.bar_access import delete_scope_bars, get_scope_overview, iter_bar_overviews
from vnpy_ashare.data.bar_health import (
    BarGapResult,
    BarHealthStatus,
    bar_meta_from_overview,
    clip_bars_from_unified_start,
    format_gap_ranges,
    format_meta_datetime,
    list_status,
)
from vnpy_ashare.data.bar_store import invalidate_bar_overview_cache
from vnpy_ashare.data.minute_periods import DEFAULT_MINUTE_DOWNLOAD_MONTHS, is_daily_scope, scope_display
from vnpy_ashare.domain.calendar import last_trading_day
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.jobs.local_fill import (
    BatchFillProgress,
    BatchFillResult,
    BatchGapFillProgress,
    BatchGapFillResult,
    count_scannable_daily_items,
    count_stale_daily_items,
    select_stale_daily_items,
)
from vnpy_ashare.ui.quotes.chart.daily import AshareChartWidget, prepare_chart_bars
from vnpy_ashare.ui.quotes.chart.tab_indices import MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.page.run_log import (
    append_run_log,
    begin_run_log,
    complete_run_log,
    fail_run_log,
)
from vnpy_ashare.ui.quotes.workers import (
    BarGapCheckWorker,
    BarsLoadWorker,
    BatchFillWorker,
    BatchGapFillWorker,
    DownloadWorker,
    InvalidBarCleanupWorker,
    LoadedBars,
    MinuteDownloadWorker,
    ScopeBarsLoadWorker,
)
from vnpy_common.ui.feedback import confirm_action

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


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


def _refresh_watchlist_signals(page: QuotesPage, vt_symbols: list[str]) -> None:
    if not page.config.show_watchlist_signals:
        return
    page._signals.refresh_symbols(vt_symbols)


def _refresh_watchlist_positions(page: QuotesPage, vt_symbols: list[str]) -> None:
    if not page.config.show_watchlist_positions:
        return
    page._positions.refresh_symbols(vt_symbols)


def _position_vt_symbols(page: QuotesPage) -> list[str]:
    service = page._get_position_service()
    if service is None:
        return []
    return [record.vt_symbol for record in service.get_items()]


def _refresh_watchlist_strategy_panels(page: QuotesPage, vt_symbols: list[str]) -> None:
    _refresh_watchlist_signals(page, vt_symbols)
    _refresh_watchlist_positions(page, vt_symbols)


class LocalDataController:
    """本地 K 线元数据、下载、缺口检查与图表加载。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def is_daily_scope(self) -> bool:
        page = self._page
        return not page.config.use_local_table or is_daily_scope(page._local_scope)

    def scope_label(self) -> str:
        return scope_display(self._page._local_scope)

    def _connect_worker_log(self, worker: QtCore.QThread) -> None:
        log_signal = getattr(worker, "log", None)
        if log_signal is not None:
            log_signal.connect(lambda message: append_run_log(self._page, message))

    def reset_meta_cache(self, *, invalidate_overview: bool = True) -> None:
        page = self._page
        if invalidate_overview:
            invalidate_bar_overview_cache()
        page.downloaded_keys = set()
        page.bar_meta = {}
        page.bar_list_status = {}

    def ensure_meta_for_items(self, items: list[StockItem]) -> None:
        """按当前页标的懒加载 K 线概览，避免全量扫描卡死 UI。"""
        page = self._page
        for item in items:
            key = (item.symbol, item.exchange)
            overview = get_scope_overview(item.symbol, item.exchange, page._local_scope)
            if overview is None:
                page.downloaded_keys.discard(key)
                page.bar_meta.pop(key, None)
                page.bar_list_status.pop(key, None)
                continue
            page.downloaded_keys.add(key)
            meta = bar_meta_from_overview(overview)
            page.bar_meta[key] = meta
            page.bar_list_status[key] = list_status(meta)

    def refresh_meta(self, *, invalidate_overview: bool = True) -> None:
        page = self._page
        self.reset_meta_cache(invalidate_overview=invalidate_overview)
        if page.config.use_local_pagination:
            self.ensure_meta_for_items(page.all_stocks)
            return
        bar_svc = page._get_bar_service()
        rows = bar_svc.iter_overviews(page._local_scope) if bar_svc else self._fallback_overviews(page._local_scope)
        for row in rows:
            key = (row.symbol, row.exchange)
            meta = bar_meta_from_overview(row)
            page.downloaded_keys.add(key)
            page.bar_meta[key] = meta
            page.bar_list_status[key] = list_status(meta)

    @staticmethod
    def _fallback_overviews(scope: str):
        """BarService 不可用时经 bar_access 枚举本地 K 线概览。"""
        return iter_bar_overviews(scope=scope)

    def on_stock_list_loaded(self) -> None:
        """本地列表加载完成后：刷新元数据、重绘表格并恢复当前选中标的图表。"""
        page = self._page
        if not page.config.use_local_table:
            return
        # Worker 已预热 overview 缓存，勿 invalidate 后在主线程全量重建。
        self.refresh_meta(invalidate_overview=False)
        page._local_filter_keyword = page.search_edit.text().strip().lower()
        page._table.apply_local_page_display()
        item = page.current_item
        if item is not None and (item.symbol, item.exchange) in page.downloaded_keys:
            page.show_kline(item)
            if page.config.show_fill_button and self.is_daily_scope():
                self.check_bar_gaps(item)

    def schedule_invalid_bar_cleanup(self) -> None:
        """后台清理无效日 K 概览，避免进入本地页时在主线程扫描全库。"""

        page = self._page
        if page._thread_active(getattr(page, "_invalid_bar_cleanup_worker", None)):
            return
        page._wait_worker_release("_invalid_bar_cleanup_worker", timeout_ms=0)

        worker = InvalidBarCleanupWorker()
        page._invalid_bar_cleanup_worker = worker

        def on_finished(removed: object) -> None:
            if page._invalid_bar_cleanup_worker is worker:
                page._invalid_bar_cleanup_worker = None
            try:
                if not page._active or not isinstance(removed, list) or not removed:
                    return
                symbols = "、".join(format_vt_symbol_cn(symbol, exchange) for symbol, exchange in removed[:5])
                suffix = "..." if len(removed) > 5 else ""
                page.status_label.setText(f"已清理 {len(removed)} 条无效日K：{symbols}{suffix}")
                if page.config.use_local_table:
                    page.load_stock_list()
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._invalid_bar_cleanup_worker is worker:
                page._invalid_bar_cleanup_worker = None
            page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def update_batch_toolbar_buttons(self) -> None:
        self.update_batch_fill_button()
        self.update_batch_gap_fill_button()
        self.update_gap_fill_button()

    def update_batch_fill_button(self) -> None:
        page = self._page
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
        page = self._page
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
        page = self._page
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
        page = self._page
        return page._thread_active(getattr(page, "_batch_fill_worker", None)) or page._thread_active(getattr(page, "_batch_gap_fill_worker", None))

    def batch_fill_stale(self) -> None:
        page = self._page
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
                _refresh_watchlist_strategy_panels(page, [item.vt_symbol for item in items])

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
        page = self._page
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
                symbols.extend(_position_vt_symbols(page))
                if symbols:
                    _refresh_watchlist_strategy_panels(page, list(dict.fromkeys(symbols)))

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
        page = self._page
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
                symbols.extend(_position_vt_symbols(page))
                if symbols:
                    _refresh_watchlist_strategy_panels(page, list(dict.fromkeys(symbols)))

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

    def on_period_changed(self) -> None:
        page = self._page
        if not page.config.use_local_table:
            return
        value = page.local_period_combo.currentData()
        if not isinstance(value, str) or value == page._local_scope:
            return
        page._local_scope = value
        page._selected_gap_result = None
        page._market_page = 0
        page._local_filter_keyword = ""
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
            if page._gap_worker is worker:
                page._gap_worker = None
            try:
                if generation != page._gap_generation:
                    return
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
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._gap_worker is worker:
                page._gap_worker = None
            try:
                if generation != page._gap_generation:
                    return
                if page.current_item is None:
                    return
                if (page.current_item.symbol, page.current_item.exchange) != key:
                    return
                self.set_chart_hint("完整性检查失败，仍可查看已有 K 线")
            finally:
                page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def clear_chart(self) -> None:
        page = self._page
        if not page.config.show_kline:
            return
        chart = page.chart
        if chart is None:
            return
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
        if self.is_daily_scope():
            bars = clip_bars_from_unified_start(bars)
        chart = page.chart
        if chart is None:
            return
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
            worker: BarsLoadWorker | ScopeBarsLoadWorker = BarsLoadWorker(item)
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
            try:
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
                if not isinstance(result, LoadedBars):
                    return
                loaded = result
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
            finally:
                page._release_worker(worker)

        def on_failed(_msg: str) -> None:
            if page._bars_worker is worker:
                page._bars_worker = None
            page._release_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
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

    def delete_selected(self) -> None:
        page = self._page
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
        page = self._page
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
        page = self._page
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
            _refresh_watchlist_strategy_panels(page, [item.vt_symbol])
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
