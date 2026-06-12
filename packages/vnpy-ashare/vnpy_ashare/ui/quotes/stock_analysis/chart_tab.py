"""个股分析：分时 / 日 K / 分 K 图表 Tab。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ui.components.chart_style import build_chart_panel_stylesheet
from vnpy_ashare.ui.quotes.chart.daily import (
    WATCHLIST_DAILY_BAR_PRESETS,
    WATCHLIST_DAILY_DEFAULT_BAR_COUNT,
    AshareChartWidget,
    create_watchlist_chart,
)
from vnpy_ashare.ui.quotes.chart.intraday import IntradayChart
from vnpy_ashare.ui.quotes.chart.ma_legend import MaLegendBar
from vnpy_ashare.ui.quotes.chart.minute_bars import MinuteBarChange, MinuteBarDiff
from vnpy_ashare.ui.quotes.chart.panel import (
    chart_tab_hint,
    is_same_item_request,
    should_apply_minute_bars,
)
from vnpy_ashare.ui.quotes.chart.tab_indices import DAILY_TAB_INDEX, MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.workers import (
    BarsLoadWorker,
    IntradayBarsWorker,
    LoadedBars,
    LoadedPeriodBars,
    MinuteBarsWorker,
)
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active
from vnpy_common.ui.theme import theme_manager

_DAILY_MISSING_HINT = "暂无本地日 K，请在数据管理页或右键菜单下载后再查看"


class StockAnalysisChartTab(QtWidgets.QWidget):
    """轻量图表区：分时 / 日 K / 分 K 子 Tab 懒加载。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        theme_manager().bind_stylesheet(self, extra=build_chart_panel_stylesheet)
        self._item: StockItem | None = None
        self._prev_close = 0.0
        self._generation = 0
        self._closing = False
        self._loaded = False

        self._intraday_worker: IntradayBarsWorker | None = None
        self._daily_worker: BarsLoadWorker | None = None
        self._minute_worker: MinuteBarsWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []

        self._intraday_error: str | None = None
        self._intraday_empty = False
        self._daily_viewport_bars = WATCHLIST_DAILY_DEFAULT_BAR_COUNT

        self._tab_bar = QtWidgets.QTabBar()
        self._tab_bar.addTab("分时")
        self._tab_bar.addTab("日K")
        self._tab_bar.addTab("分K")
        self._tab_bar.currentChanged.connect(self._on_sub_tab_changed)

        self._daily_range_combo = QtWidgets.QComboBox()
        for idx, (label, bar_count) in enumerate(WATCHLIST_DAILY_BAR_PRESETS):
            self._daily_range_combo.addItem(label, bar_count)
            if bar_count == WATCHLIST_DAILY_DEFAULT_BAR_COUNT:
                self._daily_range_combo.setCurrentIndex(idx)
        self._daily_range_combo.currentIndexChanged.connect(self._on_daily_range_changed)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(self._tab_bar, stretch=1)
        toolbar.addWidget(self._daily_range_combo)

        self._intraday_chart = IntradayChart()
        self._daily_chart = create_watchlist_chart()
        self._minute_chart = create_watchlist_chart(minute=True)
        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._intraday_chart)
        self._stack.addWidget(self._daily_chart)
        self._stack.addWidget(self._minute_chart)

        self._ma_legend = MaLegendBar()
        self._ma_legend.setVisible(False)

        self._hint = QtWidgets.QLabel("")
        self._hint.setObjectName("ChartHint")
        self._hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self._ma_legend)
        layout.addWidget(self._stack, stretch=1)
        layout.addWidget(self._hint)
        self._update_daily_range_visibility()

    def set_retired_workers(self, workers: list[QtCore.QThread]) -> None:
        self._retired_workers = workers

    def shutdown(self) -> None:
        self._closing = True
        self._generation += 1
        self._abandon_intraday_worker()
        self._abandon_daily_worker()
        self._abandon_minute_worker()

    def load(self, item: StockItem, *, quote: QuoteSnapshot | None = None) -> None:
        if self._closing:
            return
        self._loaded = True
        self._item = item
        self._apply_quote(quote)
        self._generation += 1
        self._abandon_intraday_worker()
        self._abandon_daily_worker()
        self._abandon_minute_worker()
        self._intraday_error = None
        self._intraday_empty = False
        self._intraday_chart.clear_all()
        self._daily_chart.clear_all()
        self._reset_minute_chart()
        self._update_hint()
        self._load_active_sub_tab()

    def _apply_quote(self, quote: QuoteSnapshot | None) -> None:
        if quote and quote.prev_close > 0:
            self._prev_close = quote.prev_close
        elif quote and quote.last_price > 0:
            self._prev_close = quote.last_price - quote.change_amount
        else:
            self._prev_close = 0.0

    def _update_daily_range_visibility(self) -> None:
        self._daily_range_combo.setVisible(self._tab_bar.currentIndex() == DAILY_TAB_INDEX)

    def _apply_daily_viewport(self) -> None:
        chart = self._daily_chart
        if isinstance(chart, AshareChartWidget):
            chart.set_viewport_bar_count(self._daily_viewport_bars)

    def _on_daily_range_changed(self, index: int) -> None:
        bar_count = self._daily_range_combo.itemData(index)
        if not isinstance(bar_count, int):
            return
        self._daily_viewport_bars = bar_count
        self._apply_daily_viewport()

    def _on_sub_tab_changed(self, index: int) -> None:
        self._ma_legend.setVisible(index in (DAILY_TAB_INDEX, MINUTE_TAB_INDEX))
        self._stack.setCurrentIndex(index)
        self._update_daily_range_visibility()
        self._update_hint()
        if self._loaded and not self._closing:
            self._load_active_sub_tab()

    def _update_hint(self, *, daily_missing: bool = False) -> None:
        text = chart_tab_hint(
            self._tab_bar.currentIndex(),
            daily_missing=daily_missing,
            intraday_error=self._intraday_error,
            intraday_empty=self._intraday_empty,
            minute_from_local=False,
            minute_count=0,
        )
        if text:
            self._hint.setText(text)
            self._hint.show()
        else:
            self._hint.hide()

    def _retire_worker(self, worker: QtCore.QThread) -> None:
        release_thread(self._retired_workers, worker, timeout_ms=0)

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

    def _abandon_minute_worker(self) -> None:
        worker = self._minute_worker
        if worker is None:
            return
        self._minute_worker = None
        self._retire_worker(worker)

    def _reset_minute_chart(self) -> None:
        chart = self._minute_chart
        if isinstance(chart, AshareChartWidget):
            chart.clear_all()
            chart.reset_viewport()
        else:
            chart.clear_all()

    def _load_active_sub_tab(self) -> None:
        if self._closing or self._item is None:
            return
        tab = self._tab_bar.currentIndex()
        if tab == 0:
            self._load_intraday()
        elif tab == DAILY_TAB_INDEX:
            self._load_daily()
        else:
            self._load_minute()

    def _load_intraday(self) -> None:
        if self._closing or self._item is None:
            return
        item = self._item
        target_key = (item.symbol, item.exchange)
        if thread_is_active(self._intraday_worker):
            worker = self._intraday_worker
            if worker is not None and is_same_item_request(worker, target_key=target_key):
                return
            self._abandon_intraday_worker()

        generation = self._generation
        self._intraday_chart.clear_all()
        worker = IntradayBarsWorker(item)
        self._intraday_worker = worker

        def on_finished(bars: object) -> None:
            if self._intraday_worker is worker:
                self._intraday_worker = None
            if generation != self._generation or self._closing or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key or self._tab_bar.currentIndex() != 0:
                self._retire_worker(worker)
                return
            bar_list = list(bars)
            if bar_list:
                self._intraday_empty = False
                self._intraday_error = None
                self._intraday_chart.update_bars(bar_list, prev_close=self._prev_close)
            else:
                self._intraday_empty = True
                self._intraday_error = None
                self._intraday_chart.clear_all()
            self._update_hint()
            self._retire_worker(worker)

        def on_failed(msg: str) -> None:
            if self._intraday_worker is worker:
                self._intraday_worker = None
            if generation != self._generation or self._closing:
                self._retire_worker(worker)
                return
            self._intraday_error = msg
            self._intraday_empty = False
            self._intraday_chart.clear_all()
            self._update_hint()
            self._retire_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _load_daily(self) -> None:
        if self._closing or self._item is None:
            return
        item = self._item
        target_key = (item.symbol, item.exchange)
        if thread_is_active(self._daily_worker):
            worker = self._daily_worker
            if worker is not None and is_same_item_request(worker, target_key=target_key):
                return
            self._abandon_daily_worker()

        generation = self._generation
        self._daily_chart.clear_all()
        worker = BarsLoadWorker(item)
        self._daily_worker = worker

        def on_finished(result: object) -> None:
            if self._daily_worker is worker:
                self._daily_worker = None
            if generation != self._generation or self._closing or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key or self._tab_bar.currentIndex() != DAILY_TAB_INDEX:
                self._retire_worker(worker)
                return
            if result is None:
                self._daily_chart.clear_all()
                self._hint.setText(_DAILY_MISSING_HINT)
                self._hint.show()
                self._retire_worker(worker)
                return
            loaded: LoadedBars = result
            if loaded.bars:
                self._daily_chart.replace_history(loaded.bars)
                self._apply_daily_viewport()
                self._update_hint(daily_missing=False)
            else:
                self._daily_chart.clear_all()
                self._hint.setText(_DAILY_MISSING_HINT)
                self._hint.show()
            self._retire_worker(worker)

        def on_failed(_msg: str) -> None:
            if self._daily_worker is worker:
                self._daily_worker = None
            self._hint.setText(_DAILY_MISSING_HINT)
            self._hint.show()
            self._retire_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _load_minute(self) -> None:
        if self._closing or self._item is None:
            return
        item = self._item
        target_key = (item.symbol, item.exchange)
        period = "1m"
        if thread_is_active(self._minute_worker):
            self._abandon_minute_worker()

        generation = self._generation
        self._reset_minute_chart()
        worker = MinuteBarsWorker(item, period=period, mode="full")
        self._minute_worker = worker

        def on_finished(result: object) -> None:
            if self._minute_worker is worker:
                self._minute_worker = None
            if generation != self._generation or self._closing or self._item is None:
                self._retire_worker(worker)
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                self._retire_worker(worker)
                return
            loaded = result if isinstance(result, LoadedPeriodBars) else None
            loaded_period = loaded.period if loaded else period
            if not should_apply_minute_bars(
                target_period=period,
                current_period=period,
                tab_index=self._tab_bar.currentIndex(),
                loaded_period=loaded_period,
            ):
                self._retire_worker(worker)
                return
            incoming = list(loaded.bars if loaded else result)
            change = MinuteBarChange(MinuteBarDiff.REPLACE, incoming)
            chart = self._minute_chart
            if isinstance(chart, AshareChartWidget):
                if change.bars:
                    chart.apply_bars(change)
                else:
                    self._reset_minute_chart()
            elif change.bars:
                chart.replace_history(change.bars)
            else:
                self._reset_minute_chart()
            self._update_hint()
            self._retire_worker(worker)

        def on_failed(_msg: str) -> None:
            if self._minute_worker is worker:
                self._minute_worker = None
            self._retire_worker(worker)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()
