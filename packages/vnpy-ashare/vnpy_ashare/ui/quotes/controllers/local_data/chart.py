"""K 线图表加载、缺口检查与周期切换。"""

from __future__ import annotations

from vnpy.trader.object import BarData

from vnpy_ashare.domain.data.bar_health import BarGapResult, BarHealthStatus
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.services.bar import clip_bars_from_unified_start, format_gap_ranges, format_meta_datetime, list_status
from vnpy_ashare.ui.quotes.chart.daily import AshareChartWidget, prepare_chart_bars
from vnpy_ashare.ui.quotes.controllers.local_data.base import LocalDataControllerBase
from vnpy_ashare.ui.quotes.controllers.local_data.helpers import should_apply_loaded_bars
from vnpy_ashare.ui.quotes.workers.quotes_workers import (
    BarGapCheckWorker,
    BarsLoadWorker,
    LoadedBars,
    ScopeBarsLoadWorker,
)


class LocalDataChartMixin(LocalDataControllerBase):
    def on_period_changed(self) -> None:
        page = self._p
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
        page = self._p
        if page.chart_hint is None:
            return
        if text:
            page.chart_hint.setText(text)
            page.chart_hint.show()
        else:
            page.chart_hint.hide()

    def update_coverage_hint(self, item: StockItem) -> None:
        page = self._p
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
        page = self._p
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
        page = self._p
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
        page = self._p
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
        page = self._p
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
