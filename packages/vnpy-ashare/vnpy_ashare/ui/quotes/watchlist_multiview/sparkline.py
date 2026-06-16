"""自选多维看盘迷你日 K。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.components.chart_style import apply_sparkline_plot_theme
from vnpy_common.ui.theme import theme_manager


class DailySparkline(QtWidgets.QWidget):
    """近 N 日收盘迷你折线。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WatchlistMultiSparkline")
        self._plot = pg.PlotWidget()
        self._plot.setMinimumHeight(52)
        self._plot.setMaximumHeight(64)
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        apply_sparkline_plot_theme(self._plot)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)
        theme_manager().register_callback(lambda _tokens: apply_sparkline_plot_theme(self._plot))

    def render_points(self, points: tuple[float, ...]) -> None:
        self._plot.clear()
        if len(points) < 2:
            return
        xs = list(range(len(points)))
        color = "#5b9cf5"
        if points[-1] >= points[0]:
            color = theme_manager().tokens().market_rise
        else:
            color = theme_manager().tokens().market_fall
        self._plot.plot(xs, list(points), pen=pg.mkPen(color=color, width=1.4), clear=False)

    def clear(self) -> None:
        self._plot.clear()
