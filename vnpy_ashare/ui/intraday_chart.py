"""日内分时折线图。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.chart_style import (
    AVG_LINE_COLOR,
    CHART_BG,
    PREV_CLOSE_COLOR,
    style_intraday_plot,
)
from vnpy_ashare.ui.styles import FALL_COLOR, FLAT_COLOR, RISE_COLOR


class IntradayChart(QtWidgets.QWidget):
    """价格线 + 均价线 + 昨收参考线 + 涨跌填充。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)

        self._plot = pg.PlotWidget()
        style_intraday_plot(self._plot)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._plot)

        self._fill_item: pg.FillBetweenItem | None = None
        self._baseline_curve = pg.PlotDataItem([], [], pen=pg.mkPen(width=0))
        self._plot.addItem(self._baseline_curve)
        self._price_curve = self._plot.plot(pen=pg.mkPen(RISE_COLOR, width=1.8))
        self._avg_curve = self._plot.plot(pen=pg.mkPen(AVG_LINE_COLOR, width=1))
        self._prev_close_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen(PREV_CLOSE_COLOR, style=QtCore.Qt.PenStyle.DashLine),
        )
        self._plot.addItem(self._prev_close_line)

        # LegendItem 仅支持 PlotDataItem，昨收用占位线展示样式
        self._prev_close_legend = pg.PlotDataItem(
            pen=pg.mkPen(PREV_CLOSE_COLOR, style=QtCore.Qt.PenStyle.DashLine),
        )

        self._legend = pg.LegendItem(offset=(-8, 8))
        self._legend.setParentItem(self._plot.getPlotItem())
        self._legend.addItem(self._price_curve, "价格")
        self._legend.addItem(self._avg_curve, "均价")
        self._legend.addItem(self._prev_close_legend, "昨收")

    def clear_all(self) -> None:
        self._price_curve.setData([], [])
        self._avg_curve.setData([], [])
        self._baseline_curve.setData([], [])
        self._prev_close_line.setPos(0)
        self._prev_close_line.hide()
        self._remove_fill()

    def _remove_fill(self) -> None:
        if self._fill_item is not None:
            self._plot.removeItem(self._fill_item)
            self._fill_item = None

    def _update_fill(self, xs: list[float], prices: list[float], prev_close: float) -> None:
        self._remove_fill()
        if not xs or prev_close <= 0:
            return
        self._baseline_curve.setData(xs, [prev_close] * len(xs))
        last_price = prices[-1]
        fill_color = RISE_COLOR if last_price >= prev_close else FALL_COLOR
        from vnpy.trader.ui import QtGui

        qcolor = QtGui.QColor(fill_color)
        qcolor.setAlpha(36)
        self._fill_item = pg.FillBetweenItem(
            self._baseline_curve,
            self._price_curve,
            brush=pg.mkBrush(qcolor),
        )
        self._plot.addItem(self._fill_item)

    def update_bars(self, bars: list[BarData], *, prev_close: float = 0) -> None:
        if not bars:
            self.clear_all()
            return

        xs = [bar.datetime.timestamp() for bar in bars]
        prices = [bar.close_price for bar in bars]

        cumulative_amount = 0.0
        cumulative_volume = 0.0
        avg_prices: list[float] = []
        for bar in bars:
            cumulative_amount += bar.turnover
            cumulative_volume += bar.volume
            if cumulative_volume > 0:
                avg_prices.append(cumulative_amount / cumulative_volume)
            else:
                avg_prices.append(bar.close_price)

        self._price_curve.setData(xs, prices)
        self._avg_curve.setData(xs, avg_prices)

        if prev_close > 0:
            self._prev_close_line.setPos(prev_close)
            self._prev_close_line.show()
            last_price = prices[-1]
            if last_price > prev_close:
                color = RISE_COLOR
            elif last_price < prev_close:
                color = FALL_COLOR
            else:
                color = FLAT_COLOR
            self._price_curve.setPen(pg.mkPen(color, width=1.8))
            self._update_fill(xs, prices, prev_close)
        else:
            self._prev_close_line.hide()
            self._remove_fill()

        axis = self._plot.getAxis("bottom")
        step = max(len(bars) // 8, 1)
        axis.setTicks(
            [
                [
                    (bars[index].datetime.timestamp(), bars[index].datetime.strftime("%H:%M"))
                    for index in range(0, len(bars), step)
                ]
            ]
        )

        self._plot.enableAutoRange()
