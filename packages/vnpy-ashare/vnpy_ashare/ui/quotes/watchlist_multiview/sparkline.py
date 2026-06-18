"""自选多维看盘迷你日 K。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.components.chart_style import apply_sparkline_plot_theme
from vnpy_common.ui.theme.manager import theme_manager


class DailySparkline(QtWidgets.QWidget):
    """近 N 日收盘迷你折线。"""

    _MIN_HEIGHT = 76

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WatchlistMultiSparkline")
        self.setMinimumHeight(self._MIN_HEIGHT)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._plot = pg.PlotWidget()
        self._plot.setMinimumHeight(self._MIN_HEIGHT)
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        apply_sparkline_plot_theme(self._plot)
        self._apply_compact_axes()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot, stretch=1)
        theme_manager().register_callback(lambda _tokens: self._on_theme_changed())

    def _apply_compact_axes(self) -> None:
        apply_sparkline_plot_theme(self._plot)
        item = self._plot.getPlotItem()
        item.hideAxis("bottom")
        item.hideAxis("left")
        item.showGrid(x=False, y=False)

    def _on_theme_changed(self) -> None:
        self._apply_compact_axes()
        # 主题切换后重绘当前折线颜色由卡片 apply_row 触发；此处仅刷新轴样式。

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
