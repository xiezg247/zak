"""自选页图表区：分时 / 日K / 分K。"""

from __future__ import annotations

from typing import Literal, cast

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.services.signals.runtime import resolve_display_anchor_prices, resolve_list_ref_prices
from vnpy_ashare.ui.components.chart_style import build_chart_panel_stylesheet
from vnpy_ashare.ui.quotes.chart.daily import (
    WATCHLIST_DAILY_BAR_PRESETS,
    WATCHLIST_DAILY_DEFAULT_BAR_COUNT,
    AshareChartWidget,
    create_watchlist_chart,
)
from vnpy_ashare.ui.quotes.chart.intraday import IntradayChart
from vnpy_ashare.ui.quotes.chart.ma_legend import MaLegendBar
from vnpy_ashare.ui.quotes.chart.minute_bars import (
    MinuteBarChange,
    MinuteBarDiff,
    MinuteBarSession,
    compute_minute_bar_change,
)
from vnpy_ashare.ui.quotes.chart.reference_line_legend import ReferenceLineLegendBar
from vnpy_ashare.ui.quotes.chart.tab_indices import DAILY_TAB_INDEX, MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.workers.quotes_workers import BarsLoadWorker, IntradayBarsWorker, LoadedBars, LoadedPeriodBars, MinuteBarsWorker
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active
from vnpy_common.ui.theme.manager import theme_manager

LIVE_INTRADAY_HINT = "分时来自 TickFlow 实时接口，不写入本地"
INTRADAY_EMPTY_HINT = "暂无分时数据（可能为非交易时段、标的无分钟线或 TickFlow 未返回当日数据）"
INTRADAY_FAILED_HINT = "分时加载失败：{error}"
LIVE_MINUTE_HINT = "1分K来自 TickFlow 实时接口，不写入本地"
LOCAL_MINUTE_HINT = "1分K来自本地，{start} ~ {end}，共 {count} 根"
MINUTE_MISSING_HINT = "暂无本地分K，请点击上方「下载分K到本地」（建议 ≤6 个月）"
DAILY_MISSING_HINT = "暂无本地日K，请点击上方「下载日K到本地」"


def should_apply_minute_bars(
    *,
    target_period: str,
    current_period: str,
    tab_index: int,
    loaded_period: str | None = None,
) -> bool:
    """分 K 回调是否应写入图表（周期与 Tab 须一致）。"""
    if tab_index != MINUTE_TAB_INDEX:
        return False
    if target_period != current_period:
        return False
    if loaded_period is not None and loaded_period != target_period:
        return False
    return True


def is_same_minute_request(
    worker: MinuteBarsWorker,
    *,
    period: str,
    target_key: tuple[str, Exchange],
    mode: str,
) -> bool:
    """分 K worker 是否仍在为同一标的、周期与模式加载。"""
    worker_key = (worker.item.symbol, worker.item.exchange)
    return worker.period == period and worker_key == target_key and worker.mode == mode


def is_same_item_request(
    worker: QtCore.QThread,
    *,
    target_key: tuple[str, Exchange],
) -> bool:
    """worker 是否仍在为同一标的加载（分时 / 日 K）。"""
    item = getattr(worker, "item", None)
    if item is None:
        return False
    return (item.symbol, item.exchange) == target_key


def chart_tab_hint(
    tab_index: int,
    *,
    daily_missing: bool = False,
    intraday_error: str | None = None,
    intraday_empty: bool = False,
    minute_from_local: bool = False,
    minute_start: str | None = None,
    minute_end: str | None = None,
    minute_count: int = 0,
) -> str | None:
    if tab_index == 0:
        if intraday_error:
            return INTRADAY_FAILED_HINT.format(error=intraday_error)
        if intraday_empty:
            return INTRADAY_EMPTY_HINT
        return LIVE_INTRADAY_HINT
    if tab_index == MINUTE_TAB_INDEX:
        if minute_from_local and minute_start and minute_end:
            return LOCAL_MINUTE_HINT.format(
                start=minute_start,
                end=minute_end,
                count=minute_count,
            )
        return LIVE_MINUTE_HINT
    if tab_index == DAILY_TAB_INDEX and daily_missing:
        return DAILY_MISSING_HINT
    return None


class ChartPanel(QtWidgets.QWidget):
    """Tab 切换 + 懒加载 + 3 秒刷新当前 Tab。"""

    tab_changed = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChartPanel")
        theme_manager().bind_stylesheet(self, extra=build_chart_panel_stylesheet)
        self._item: StockItem | None = None
        self._prev_close = 0.0
        self._last_quote: QuoteSnapshot | None = None
        self._generation = 0
        self._active = True

        self._minute_session = MinuteBarSession()
        self._minute_loaded_period: str | None = None
        self._minute_loaded_key: tuple[str, Exchange] | None = None
        self._minute_request_id = 0
        self._intraday_error: str | None = None
        self._intraday_empty = False
        self._daily_viewport_bars = WATCHLIST_DAILY_DEFAULT_BAR_COUNT
        self._signal_snapshot: SignalSnapshot | None = None

        self._intraday_worker: IntradayBarsWorker | None = None
        self._minute_worker: MinuteBarsWorker | None = None
        self._daily_worker: BarsLoadWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []

        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.addTab("分时")
        self.tab_bar.addTab("日K")
        self.tab_bar.addTab("分K")
        self.tab_bar.currentChanged.connect(self._on_tab_changed)

        self._daily_range_combo = QtWidgets.QComboBox()
        self._daily_range_combo.setObjectName("DailyRangeCombo")
        for idx, (label, bar_count) in enumerate(WATCHLIST_DAILY_BAR_PRESETS):
            self._daily_range_combo.addItem(label, bar_count)
            if bar_count == WATCHLIST_DAILY_DEFAULT_BAR_COUNT:
                self._daily_range_combo.setCurrentIndex(idx)
        self._daily_range_combo.currentIndexChanged.connect(self._on_daily_range_changed)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(self.tab_bar, stretch=1)
        toolbar.addWidget(self._daily_range_combo)

        self.intraday_chart = IntradayChart()
        self.daily_chart = create_watchlist_chart()
        self.minute_chart = create_watchlist_chart(minute=True)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.intraday_chart)
        self.stack.addWidget(self.daily_chart)
        self.stack.addWidget(self.minute_chart)

        self.ma_legend = MaLegendBar()
        self.ma_legend.setVisible(False)

        self.ref_legend = ReferenceLineLegendBar()
        self.ref_legend.setVisible(False)

        self.hint_label = QtWidgets.QLabel()
        self.hint_label.setObjectName("ChartHint")
        self.hint_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.hint_label.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self.ma_legend)
        layout.addWidget(self.ref_legend)
        layout.addWidget(self.stack, stretch=1)
        layout.addWidget(self.hint_label)
        self._update_daily_range_visibility()

    def _update_daily_range_visibility(self) -> None:
        self._daily_range_combo.setVisible(self.tab_bar.currentIndex() == DAILY_TAB_INDEX)

    def _apply_daily_viewport(self) -> None:
        chart = self.daily_chart
        if isinstance(chart, AshareChartWidget):
            chart.set_viewport_bar_count(self._daily_viewport_bars)

    def _on_daily_range_changed(self, index: int) -> None:
        bar_count = self._daily_range_combo.itemData(index)
        if not isinstance(bar_count, int):
            return
        self._daily_viewport_bars = bar_count
        self._apply_daily_viewport()

    _thread_active = staticmethod(thread_is_active)

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            self._generation += 1
            self._abandon_intraday_worker()
            self._abandon_minute_worker()
            self._abandon_daily_worker()

    def current_tab_index(self) -> int:
        return self.tab_bar.currentIndex()

    def update_quote(self, quote: QuoteSnapshot | None) -> None:
        self._last_quote = quote
        if quote and quote.prev_close > 0:
            self._prev_close = quote.prev_close
        elif quote and quote.last_price > 0:
            self._prev_close = quote.last_price - quote.change_amount

    def apply_signal_reference(
        self,
        snapshot: SignalSnapshot | None,
        *,
        quote: QuoteSnapshot | None = None,
        fast_window: int = 10,
        slow_window: int = 20,
    ) -> None:
        """日 K 叠加策略结构锚点、动作参考价与现价水平线。"""
        self._signal_snapshot = snapshot
        if snapshot is None:
            self.daily_chart.clear_reference_lines()
            self.minute_chart.clear_reference_lines()
            self.ref_legend.clear()
            self._update_ref_legend_visibility()
            return
        last_price = quote.last_price if quote and quote.last_price > 0 else None
        ref_buy, ref_sell, _ = resolve_display_anchor_prices(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        action_buy, action_sell = resolve_list_ref_prices(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        self.daily_chart.set_reference_lines(
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            last_price=last_price,
            action_buy=action_buy,
            action_sell=action_sell,
        )
        self.minute_chart.set_reference_lines(
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            last_price=last_price,
            action_buy=action_buy,
            action_sell=action_sell,
        )
        self.ref_legend.set_reference_lines(
            ref_buy=ref_buy,
            ref_sell=ref_sell,
            last_price=last_price,
        )
        self._update_ref_legend_visibility()

    def _update_ref_legend_visibility(self) -> None:
        on_kline = self.tab_bar.currentIndex() in (DAILY_TAB_INDEX, MINUTE_TAB_INDEX)
        has_lines = self.ref_legend.has_entries()
        self.ref_legend.setVisible(on_kline and has_lines)

    def load_item(self, item: StockItem | None, *, quote: QuoteSnapshot | None = None) -> None:
        is_new = item is not None and (self._item is None or (item.symbol, item.exchange) != (self._item.symbol, self._item.exchange))
        self._item = item
        self.update_quote(quote)
        self._generation += 1
        self._abandon_intraday_worker()
        self._abandon_minute_worker()
        self._abandon_daily_worker()
        self._minute_session.reset()
        self._minute_loaded_period = None
        self._minute_loaded_key = None
        self._minute_request_id += 1
        self._intraday_error = None
        self._intraday_empty = False
        if is_new:
            self._signal_snapshot = None
            self.daily_chart.clear_reference_lines()
            self.minute_chart.clear_reference_lines()
            self.ref_legend.clear()
            if self.tab_bar.currentIndex() == MINUTE_TAB_INDEX:
                self._reset_minute_chart()
            else:
                self._apply_default_tab()
        self.ma_legend.setVisible(self.tab_bar.currentIndex() in (1, 2))
        self._update_ref_legend_visibility()
        self._update_daily_range_visibility()
        self._update_hint()
        self.tab_changed.emit(self.tab_bar.currentIndex())
        self._load_active_tab()

    def current_period(self) -> str:
        return "1m"

    def current_period_label(self) -> str:
        return "1分"

    def _sync_minute_hint_from_session(self) -> None:
        self._update_hint()

    def _update_hint(self, *, daily_missing: bool = False) -> None:
        session = self._minute_session
        text = chart_tab_hint(
            self.tab_bar.currentIndex(),
            daily_missing=daily_missing,
            intraday_error=self._intraday_error,
            intraday_empty=self._intraday_empty,
            minute_from_local=session.from_local,
            minute_start=session.start_text or None,
            minute_end=session.end_text or None,
            minute_count=session.bar_count(),
        )
        if text:
            self.hint_label.setText(text)
            self.hint_label.show()
        else:
            self.hint_label.hide()

    def _apply_default_tab(self) -> None:
        # 自选页以分时为主；非交易时段也展示当日已产生的分时数据。
        tab = 0
        if self.tab_bar.currentIndex() == tab:
            return
        self.tab_bar.blockSignals(True)
        try:
            self.tab_bar.setCurrentIndex(tab)
            self.stack.setCurrentIndex(tab)
        finally:
            self.tab_bar.blockSignals(False)

    def refresh_active(self) -> None:
        if self._item is None:
            return
        if self.tab_bar.currentIndex() == MINUTE_TAB_INDEX:
            if self._thread_active(self._minute_worker):
                return
            item = self._item
            period = self.current_period()
            session_key = (item.symbol, item.exchange, period)
            if self._minute_session.from_local:
                if self._minute_session.overview_unchanged(item.symbol, item.exchange, period):
                    return
                self._load_minute(quiet=True, mode="full")
                return
            if not is_ashare_trading_session():
                return
            if self._minute_session.matches_key(session_key):
                self._load_minute(quiet=True, mode="tail")
                return
            self._load_minute(quiet=True, mode="full")
            return
        self._load_active_tab(quiet=True)

    def _on_tab_changed(self, index: int) -> None:
        self.ma_legend.setVisible(index in (1, 2))
        self._update_ref_legend_visibility()
        self._update_daily_range_visibility()
        self.stack.setCurrentIndex(index)
        self._update_hint()
        self.tab_changed.emit(index)
        self._load_active_tab()

    def _reset_minute_chart(self) -> None:
        chart = self.minute_chart
        if isinstance(chart, AshareChartWidget):
            chart.clear_all()
            chart.reset_viewport()
        else:
            chart.clear_all()

    def _retire_worker(self, worker: QtCore.QThread) -> None:
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def _abandon_minute_worker(self) -> None:
        worker = self._minute_worker
        if worker is None:
            return
        self._minute_worker = None
        self._retire_worker(worker)

    def _abandon_intraday_worker(self) -> None:
        worker = self._intraday_worker
        if worker is None:
            return
        self._intraday_worker = None
        self._retire_worker(worker)

    def _abandon_daily_worker(self) -> None:
        worker = self._daily_worker
        if worker is None:
            return
        self._daily_worker = None
        self._retire_worker(worker)

    def _load_active_tab(self, *, quiet: bool = False) -> None:
        if not self._active or self._item is None:
            return

        tab = self.tab_bar.currentIndex()
        if tab == 0:
            self._load_intraday(quiet=quiet)
        elif tab == 1:
            self._load_daily(quiet=quiet)
        else:
            self._load_minute(quiet=quiet)

    def _load_intraday(self, *, quiet: bool = False) -> None:
        if not self._active or self._item is None:
            return

        item = self._item
        target_key = (item.symbol, item.exchange)
        if self._thread_active(self._intraday_worker):
            worker = self._intraday_worker
            if worker is not None and is_same_item_request(
                worker,
                target_key=target_key,
            ):
                return
            self._abandon_intraday_worker()

        generation = self._generation
        if not quiet:
            self.intraday_chart.clear_all()

        worker = IntradayBarsWorker(item)
        self._intraday_worker = worker

        def on_finished(bars: object) -> None:
            if self._intraday_worker is worker:
                self._intraday_worker = None
            if generation != self._generation:
                self._retire_worker(worker)
                return
            if not self._active or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                self._retire_worker(worker)
                return
            if self.tab_bar.currentIndex() != 0:
                self._retire_worker(worker)
                return
            if not isinstance(bars, list):
                self._retire_worker(worker)
                return
            bar_list = cast(list[BarData], bars)
            if bar_list:
                self._intraday_empty = False
                self._intraday_error = None
                self.intraday_chart.update_bars(bar_list, prev_close=self._prev_close)
            else:
                self._intraday_empty = True
                self._intraday_error = None
                self.intraday_chart.clear_all()
            self._update_hint()
            self._retire_worker(worker)

        def on_failed(msg: str) -> None:
            if self._intraday_worker is worker:
                self._intraday_worker = None
            if generation != self._generation:
                self._retire_worker(worker)
                return
            if not self._active or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                self._retire_worker(worker)
                return
            if self.tab_bar.currentIndex() != 0:
                self._retire_worker(worker)
                return
            self._intraday_error = msg
            self._intraday_empty = False
            self.intraday_chart.clear_all()
            self._update_hint()
            self._retire_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _load_daily(self, *, quiet: bool = False) -> None:
        if not self._active or self._item is None:
            return

        item = self._item
        target_key = (item.symbol, item.exchange)
        if self._thread_active(self._daily_worker):
            worker = self._daily_worker
            if worker is not None and is_same_item_request(
                worker,
                target_key=target_key,
            ):
                return
            self._abandon_daily_worker()

        generation = self._generation
        if not quiet:
            self.daily_chart.clear_all()

        worker = BarsLoadWorker(item)
        self._daily_worker = worker

        def on_finished(result: object) -> None:
            if self._daily_worker is worker:
                self._daily_worker = None
            if generation != self._generation:
                self._retire_worker(worker)
                return
            if not self._active or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                self._retire_worker(worker)
                return
            if self.tab_bar.currentIndex() != 1:
                self._retire_worker(worker)
                return
            if result is None:
                self.daily_chart.clear_all()
                self._update_hint(daily_missing=True)
                self._retire_worker(worker)
                return
            if not isinstance(result, LoadedBars):
                self._retire_worker(worker)
                return
            loaded = result
            if loaded.bars:
                self.daily_chart.replace_history(loaded.bars)
                self._apply_daily_viewport()
                if self._signal_snapshot is not None:
                    self.apply_signal_reference(self._signal_snapshot, quote=self._last_quote)
                self._update_hint(daily_missing=False)
            else:
                self.daily_chart.clear_all()
                self._update_hint(daily_missing=True)
            self._retire_worker(worker)

        def on_failed(_msg: str) -> None:
            if self._daily_worker is worker:
                self._daily_worker = None
            self._retire_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _load_minute(
        self,
        *,
        quiet: bool = False,
        mode: Literal["full", "tail"] = "full",
    ) -> None:
        if not self._active or self._item is None:
            return

        period = self.current_period()
        item = self._item
        target_key = (item.symbol, item.exchange)
        session_key = (item.symbol, item.exchange, period)

        if mode == "full" and not quiet and self._minute_session.matches_key(session_key):
            if self._minute_session.from_local and not self._minute_session.overview_unchanged(
                item.symbol,
                item.exchange,
                period,
            ):
                pass
            else:
                self._sync_minute_hint_from_session()
                return

        if self._thread_active(self._minute_worker):
            minute_worker = self._minute_worker
            if minute_worker is not None and is_same_minute_request(
                minute_worker,
                period=period,
                target_key=target_key,
                mode=mode,
            ):
                return
            self._minute_request_id += 1
            self._abandon_minute_worker()

        generation = self._generation
        self._minute_request_id += 1
        request_id = self._minute_request_id
        target_period = period

        if not quiet:
            self._reset_minute_chart()

        worker = MinuteBarsWorker(item, period=target_period, mode=mode)
        self._minute_worker = worker

        def on_finished(result: object) -> None:
            if self._minute_worker is worker:
                self._minute_worker = None
            if generation != self._generation:
                self._retire_worker(worker)
                return
            if request_id != self._minute_request_id:
                self._retire_worker(worker)
                return
            if not self._active or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                self._retire_worker(worker)
                return

            loaded = result if isinstance(result, LoadedPeriodBars) else None
            loaded_period = loaded.period if loaded else None
            if not should_apply_minute_bars(
                target_period=target_period,
                current_period=self.current_period(),
                tab_index=self.tab_bar.currentIndex(),
                loaded_period=loaded_period,
            ):
                self._retire_worker(worker)
                return

            if loaded is not None:
                incoming = list(loaded.bars)
            elif isinstance(result, list):
                incoming = cast(list[BarData], result)
            else:
                incoming = []
            if mode == "full" or not self._minute_session.matches_key(session_key):
                change = MinuteBarChange(diff=MinuteBarDiff.REPLACE, bars=incoming)
            else:
                change = compute_minute_bar_change(self._minute_session.bars, incoming)

            if change.diff == MinuteBarDiff.NOOP:
                self._sync_minute_hint_from_session()
                self._retire_worker(worker)
                return

            if loaded and loaded.from_local and loaded.start and loaded.end:
                self._minute_session.apply_loaded(
                    key=session_key,
                    bars=change.bars,
                    from_local=True,
                    start=loaded.start,
                    end=loaded.end,
                )
            elif mode == "full":
                self._minute_session.apply_loaded(
                    key=session_key,
                    bars=change.bars,
                    from_local=False,
                    start=None,
                    end=None,
                )
            else:
                self._minute_session.adopt_bars(change.bars)

            self._sync_minute_hint_from_session()
            chart = self.minute_chart
            if isinstance(chart, AshareChartWidget):
                if change.bars:
                    chart.apply_bars(change)
                    self._minute_loaded_period = target_period
                    self._minute_loaded_key = target_key
                    if self._signal_snapshot is not None:
                        self.apply_signal_reference(self._signal_snapshot, quote=self._last_quote)
                else:
                    self._reset_minute_chart()
                    self._minute_session.reset()
                    self._minute_loaded_period = None
                    self._minute_loaded_key = None
            elif change.bars:
                chart.replace_history(change.bars)
                self._minute_loaded_period = target_period
                self._minute_loaded_key = target_key
            else:
                self._reset_minute_chart()
                self._minute_session.reset()
                self._minute_loaded_period = None
                self._minute_loaded_key = None
            self._retire_worker(worker)

        def on_failed(_msg: str) -> None:
            if self._minute_worker is worker:
                self._minute_worker = None
            self._retire_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()
