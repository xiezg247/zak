"""自选页图表区：分时 / 日K / 分K。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ui.chart_style import CHART_PANEL_STYLESHEET
from vnpy_ashare.ui.intraday_chart import IntradayChart
from vnpy_ashare.ui.ma_legend import MaLegendBar
from vnpy_ashare.ui.quotes_chart import (
    AshareChartWidget,
    WATCHLIST_DAILY_BAR_PRESETS,
    WATCHLIST_DAILY_DEFAULT_BAR_COUNT,
    create_watchlist_chart,
    prepare_chart_bars,
)
from vnpy_ashare.ui.styles import NAV_MUTED_COLOR
from vnpy_ashare.ui.worker import (
    BarsLoadWorker,
    IntradayBarsWorker,
    LoadedBars,
    LoadedPeriodBars,
    MinuteBarsWorker,
)

LIVE_INTRADAY_HINT = "分时来自 TickFlow 实时接口，不写入本地"
INTRADAY_EMPTY_HINT = "暂无分时数据（可能为非交易时段、标的无分钟线或 TickFlow 未返回当日数据）"
INTRADAY_FAILED_HINT = "分时加载失败：{error}"
LIVE_MINUTE_HINT = "1分K来自 TickFlow 实时接口，不写入本地"
LOCAL_MINUTE_HINT = "1分K来自本地，{start} ~ {end}，共 {count} 根"
MINUTE_MISSING_HINT = "暂无本地分K，请点击上方「下载分K到本地」（建议 ≤6 个月）"
DAILY_MISSING_HINT = "暂无本地日K，请点击上方「下载日K到本地」"
DAILY_TAB_INDEX = 1
MINUTE_TAB_INDEX = 2


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


def retain_thread_until_finished(
    retired: list[QtCore.QThread],
    worker: QtCore.QThread,
) -> None:
    """保留 QThread 引用直至 run() 结束，避免 destroy-while-running。"""
    if worker in retired:
        return
    retired.append(worker)

    def _release(*_args: object) -> None:
        try:
            retired.remove(worker)
        except ValueError:
            pass

    for signal_name in ("finished", "failed"):
        signal = getattr(worker, signal_name, None)
        if signal is None:
            continue
        try:
            signal.connect(_release)
        except (RuntimeError, TypeError):
            pass


def is_same_minute_request(
    worker: MinuteBarsWorker,
    *,
    period: str,
    target_key: tuple[str, Exchange],
) -> bool:
    """分 K worker 是否仍在为同一标的、同一周期加载。"""
    worker_key = (worker.item.symbol, worker.item.exchange)
    return worker.period == period and worker_key == target_key


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
        self.setStyleSheet(CHART_PANEL_STYLESHEET)
        self._item: StockItem | None = None
        self._prev_close = 0.0
        self._generation = 0
        self._active = True

        self._minute_from_local = False
        self._minute_start_text = ""
        self._minute_end_text = ""
        self._minute_count = 0
        self._minute_loaded_period: str | None = None
        self._minute_loaded_key: tuple[str, Exchange] | None = None
        self._minute_request_id = 0
        self._intraday_error: str | None = None
        self._intraday_empty = False
        self._daily_viewport_bars = WATCHLIST_DAILY_DEFAULT_BAR_COUNT

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

        self.hint_label = QtWidgets.QLabel()
        self.hint_label.setObjectName("ChartHint")
        self.hint_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(f"color: {NAV_MUTED_COLOR}; font-size: 12px; padding: 4px 8px;")
        self.hint_label.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self.ma_legend)
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

    @staticmethod
    def _thread_active(worker: QtCore.QThread | None) -> bool:
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

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
        if quote and quote.prev_close > 0:
            self._prev_close = quote.prev_close
        elif quote and quote.last_price > 0:
            self._prev_close = quote.last_price - quote.change_amount

    def load_item(self, item: StockItem | None, *, quote: QuoteSnapshot | None = None) -> None:
        is_new = (
            item is not None
            and (
                self._item is None
                or (item.symbol, item.exchange) != (self._item.symbol, self._item.exchange)
            )
        )
        self._item = item
        self.update_quote(quote)
        self._generation += 1
        self._abandon_intraday_worker()
        self._abandon_minute_worker()
        self._abandon_daily_worker()
        self._minute_from_local = False
        self._minute_start_text = ""
        self._minute_end_text = ""
        self._minute_count = 0
        self._minute_loaded_period = None
        self._minute_loaded_key = None
        self._minute_request_id += 1
        self._intraday_error = None
        self._intraday_empty = False
        if is_new:
            if self.tab_bar.currentIndex() == MINUTE_TAB_INDEX:
                self._reset_minute_chart()
            else:
                self._apply_default_tab()
        self.ma_legend.setVisible(self.tab_bar.currentIndex() in (1, 2))
        self._update_daily_range_visibility()
        self._update_hint()
        self.tab_changed.emit(self.tab_bar.currentIndex())
        self._load_active_tab()

    def current_period(self) -> str:
        return "1m"

    def current_period_label(self) -> str:
        return "1分"

    def _update_hint(self, *, daily_missing: bool = False) -> None:
        text = chart_tab_hint(
            self.tab_bar.currentIndex(),
            daily_missing=daily_missing,
            intraday_error=self._intraday_error,
            intraday_empty=self._intraday_empty,
            minute_from_local=self._minute_from_local,
            minute_start=self._minute_start_text or None,
            minute_end=self._minute_end_text or None,
            minute_count=self._minute_count,
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
            self._load_minute(quiet=False)
            return
        self._load_active_tab(quiet=True)

    def _on_tab_changed(self, index: int) -> None:
        self.ma_legend.setVisible(index in (1, 2))
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
        retain_thread_until_finished(self._retired_workers, worker)

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
            if generation != self._generation:
                if self._intraday_worker is worker:
                    self._intraday_worker = None
                return
            if self._intraday_worker is worker:
                self._intraday_worker = None
            if not self._active or self._item is None:
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                return
            if self.tab_bar.currentIndex() != 0:
                return
            bar_list = list(bars)
            if bar_list:
                self._intraday_empty = False
                self._intraday_error = None
                self.intraday_chart.update_bars(bar_list, prev_close=self._prev_close)
            else:
                self._intraday_empty = True
                self._intraday_error = None
                self.intraday_chart.clear_all()
            self._update_hint()

        def on_failed(msg: str) -> None:
            if self._intraday_worker is worker:
                self._intraday_worker = None
            if generation != self._generation:
                return
            if not self._active or self._item is None:
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                return
            if self.tab_bar.currentIndex() != 0:
                return
            self._intraday_error = msg
            self._intraday_empty = False
            self.intraday_chart.clear_all()
            self._update_hint()

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
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
            if generation != self._generation:
                if self._daily_worker is worker:
                    self._daily_worker = None
                return
            if self._daily_worker is worker:
                self._daily_worker = None
            if not self._active or self._item is None:
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                return
            if self.tab_bar.currentIndex() != 1:
                return
            if result is None:
                self.daily_chart.clear_all()
                self._update_hint(daily_missing=True)
                return
            loaded: LoadedBars = result
            if loaded.bars:
                self.daily_chart.replace_history(loaded.bars)
                self._apply_daily_viewport()
                self._update_hint(daily_missing=False)
            else:
                self.daily_chart.clear_all()
                self._update_hint(daily_missing=True)

        def on_failed(_msg: str) -> None:
            if self._daily_worker is worker:
                self._daily_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _load_minute(self, *, quiet: bool = False) -> None:
        if not self._active or self._item is None:
            return

        period = self.current_period()
        item = self._item
        target_key = (item.symbol, item.exchange)

        if self._thread_active(self._minute_worker):
            if is_same_minute_request(
                self._minute_worker,
                period=period,
                target_key=target_key,
            ):
                return
            self._minute_request_id += 1
            self._abandon_minute_worker()

        generation = self._generation
        self._minute_request_id += 1
        request_id = self._minute_request_id
        target_period = period

        self._reset_minute_chart()

        worker = MinuteBarsWorker(item, period=target_period)
        self._minute_worker = worker

        def on_finished(result: object) -> None:
            if generation != self._generation:
                if self._minute_worker is worker:
                    self._minute_worker = None
                return
            if request_id != self._minute_request_id:
                if self._minute_worker is worker:
                    self._minute_worker = None
                return
            if self._minute_worker is worker:
                self._minute_worker = None
            if not self._active or self._item is None:
                return
            if (self._item.symbol, self._item.exchange) != target_key:
                return

            loaded = result if isinstance(result, LoadedPeriodBars) else None
            loaded_period = loaded.period if loaded else None
            if not should_apply_minute_bars(
                target_period=target_period,
                current_period=self.current_period(),
                tab_index=self.tab_bar.currentIndex(),
                loaded_period=loaded_period,
            ):
                return

            bar_list = prepare_chart_bars(loaded.bars if loaded else list(result))
            if loaded and loaded.from_local and loaded.start and loaded.end:
                self._minute_from_local = True
                self._minute_start_text = loaded.start.strftime("%Y-%m-%d")
                self._minute_end_text = loaded.end.strftime("%Y-%m-%d %H:%M")
                self._minute_count = len(bar_list)
            else:
                self._minute_from_local = False
                self._minute_start_text = ""
                self._minute_end_text = ""
                self._minute_count = 0
            self._update_hint()
            if bar_list:
                self.minute_chart.replace_history(bar_list)
                self._minute_loaded_period = target_period
                self._minute_loaded_key = target_key
            else:
                self._reset_minute_chart()
                self._minute_loaded_period = None
                self._minute_loaded_key = None

        def on_failed(_msg: str) -> None:
            if self._minute_worker is worker:
                self._minute_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()
