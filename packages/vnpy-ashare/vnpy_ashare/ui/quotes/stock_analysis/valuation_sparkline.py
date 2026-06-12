"""个股分析：估值历史迷你图。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.storage.repositories.valuation import ValuationRow
from vnpy_ashare.ui.components.chart_style import apply_sparkline_plot_theme
from vnpy_common.ui.panel_widgets import configure_document_tab_widget, content_card, section_title


class ValuationSparkline(QtWidgets.QWidget):
    """PE / PB 近 N 日折线。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._pe_plot = pg.PlotWidget()
        self._pb_plot = pg.PlotWidget()
        for plot, title in ((self._pe_plot, "PE (TTM)"), (self._pb_plot, "PB")):
            plot.setMinimumHeight(88)
            plot.setMaximumHeight(120)
            plot.showGrid(x=True, y=True, alpha=0.15)
            plot.setMenuEnabled(False)
            plot.hideButtons()
            plot.setLabel("left", title)
            apply_sparkline_plot_theme(plot)

        tabs = configure_document_tab_widget(QtWidgets.QTabWidget())
        tabs.addTab(self._pe_plot, "PE")
        tabs.addTab(self._pb_plot, "PB")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)

    def show_loading(self) -> None:
        self._pe_plot.clear()
        self._pb_plot.clear()

    def render(self, history: list[ValuationRow]) -> None:
        self._pe_plot.clear()
        self._pb_plot.clear()
        if not history:
            return

        ordered = sorted(history, key=lambda row: row.trade_date)
        pe_series = [row.pe_ttm for row in ordered if row.pe_ttm is not None and row.pe_ttm > 0]
        pb_series = [row.pb for row in ordered if row.pb is not None and row.pb > 0]

        if pe_series:
            pe_xs = list(range(len(pe_series)))
            self._pe_plot.plot(pe_xs, pe_series, pen=pg.mkPen(color="#5b9cf5", width=1.5), clear=False)

        if pb_series:
            pb_xs = list(range(len(pb_series)))
            self._pb_plot.plot(pb_xs, pb_series, pen=pg.mkPen(color="#c9a227", width=1.5), clear=False)


class ValuationHistorySection(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._chart = ValuationSparkline()
        self._hint = QtWidgets.QLabel("")
        self._hint.setObjectName("PageHint")
        page = content_card(
            section_title("估值历史（近 120 交易日）"),
            self._hint,
            self._chart,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

    def show_idle(self, message: str = "切换到本 Tab 时加载") -> None:
        self._hint.setText(message)
        self._chart.show_loading()

    def show_loading(self) -> None:
        self._hint.setText("加载中…")
        self._chart.show_loading()

    def render(self, history: list[ValuationRow]) -> None:
        if not history:
            self._hint.setText("暂无本地估值历史（打开弹窗或定时任务会同步）")
            self._chart.show_loading()
            return
        latest = max(row.trade_date for row in history)
        self._hint.setText(f"样本 {len(history)} 条 · 最新 {latest}")
        self._chart.render(history)
