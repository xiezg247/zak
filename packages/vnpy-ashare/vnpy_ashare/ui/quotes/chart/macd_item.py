"""K 线 MACD 副图。"""

from __future__ import annotations

import math
from typing import Protocol

import pyqtgraph as pg
from vnpy.chart.item import ChartItem
from vnpy.chart.manager import BarManager
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtGui

from vnpy_ashare.domain.tech.indicators import calc_macd
from vnpy_ashare.ui.components.chart_style import FALL_RGB, RISE_RGB


class _MacdValueLineItem(ChartItem):
    def __init__(self, manager: BarManager, *, color: str, label: str) -> None:
        super().__init__(manager)
        self._pen = pg.mkPen(color=color, width=1)
        self._label = label
        self._values: list[float] = []

    def _rebuild(self) -> None:
        closes = [bar.close_price for bar in self._manager.get_all_bars()]
        dif, dea, _hist = calc_macd(closes)
        if self._label == "DIF":
            self._values = dif
        elif self._label == "DEA":
            self._values = dea
        else:
            self._values = []

    def update_history(self, history: list[BarData]) -> None:
        super().update_history(history)
        self._rebuild()

    def update_bar(self, bar: BarData) -> None:
        super().update_bar(bar)
        self._rebuild()

    def clear_all(self) -> None:
        super().clear_all()
        self._values = []

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        return QtGui.QPicture()

    def _draw_item_picture(self, min_ix: int, max_ix: int) -> None:
        self._item_picuture = QtGui.QPicture()
        painter = QtGui.QPainter(self._item_picuture)
        painter.setPen(self._pen)
        end = min(max_ix, len(self._values))
        for ix in range(max(min_ix, 1), end):
            prev_value = self._values[ix - 1]
            value = self._values[ix]
            if math.isnan(prev_value) or math.isnan(value):
                continue
            painter.drawLine(
                QtCore.QPointF(ix - 1, prev_value),
                QtCore.QPointF(ix, value),
            )
        painter.end()

    def boundingRect(self) -> QtCore.QRectF:
        count = self._manager.get_count()
        if count <= 0:
            return QtCore.QRectF()
        y_min, y_max = self.get_y_range()
        span = max(y_max - y_min, 1.0)
        return QtCore.QRectF(0.0, y_min, float(count), span)

    def get_y_range(
        self,
        min_ix: int | None = None,
        max_ix: int | None = None,
    ) -> tuple[float, float]:
        values = self._values
        if min_ix is not None and max_ix is not None:
            values = values[min_ix:max_ix]
        valid = [value for value in values if not math.isnan(value)]
        if not valid:
            return -1.0, 1.0
        return min(valid), max(valid)

    def get_info_text(self, ix: int) -> str:
        if ix < 0 or ix >= len(self._values):
            return ""
        value = self._values[ix]
        if math.isnan(value):
            return ""
        return f"{self._label} {value:.3f}"


class MacdHistItem(ChartItem):
    """MACD 柱。"""

    def __init__(self, manager: BarManager) -> None:
        super().__init__(manager)
        self._values: list[float] = []

    def _rebuild(self) -> None:
        closes = [bar.close_price for bar in self._manager.get_all_bars()]
        _dif, _dea, hist = calc_macd(closes)
        self._values = hist

    def update_history(self, history: list[BarData]) -> None:
        super().update_history(history)
        self._rebuild()

    def update_bar(self, bar: BarData) -> None:
        super().update_bar(bar)
        self._rebuild()

    def clear_all(self) -> None:
        super().clear_all()
        self._values = []

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        picture = QtGui.QPicture()
        if ix >= len(self._values):
            return picture
        value = self._values[ix]
        if math.isnan(value) or value == 0:
            return picture
        painter = QtGui.QPainter(picture)
        color = RISE_RGB if value >= 0 else FALL_RGB
        painter.setPen(QtGui.QPen(QtGui.QColor(*color)))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color)))
        width = 0.35
        if value >= 0:
            painter.drawRect(QtCore.QRectF(ix - width, 0, width * 2, value))
        else:
            painter.drawRect(QtCore.QRectF(ix - width, value, width * 2, -value))
        painter.end()
        return picture

    def boundingRect(self) -> QtCore.QRectF:
        count = self._manager.get_count()
        if count <= 0:
            return QtCore.QRectF()
        y_min, y_max = self.get_y_range()
        span = max(abs(y_min), abs(y_max), 1.0)
        return QtCore.QRectF(0.0, -span, float(count), span * 2)

    def get_y_range(
        self,
        min_ix: int | None = None,
        max_ix: int | None = None,
    ) -> tuple[float, float]:
        values = self._values
        if min_ix is not None and max_ix is not None:
            values = values[min_ix:max_ix]
        valid = [value for value in values if not math.isnan(value)]
        if not valid:
            return -1.0, 1.0
        return min(valid), max(valid)

    def get_info_text(self, ix: int) -> str:
        if ix < 0 or ix >= len(self._values):
            return ""
        value = self._values[ix]
        if math.isnan(value):
            return ""
        return f"MACD {value:.3f}"


def _line_item_class(color: str, label: str) -> type[_MacdValueLineItem]:
    class _Item(_MacdValueLineItem):
        def __init__(self, manager: BarManager) -> None:
            super().__init__(manager, color=color, label=label)

    _Item.__name__ = f"Macd{label}Item"
    return _Item


class _ChartItemHost(Protocol):
    def add_item(self, item_class: type, name: str, plot_name: str) -> None: ...


def register_macd_items(chart: _ChartItemHost) -> None:
    chart.add_item(_line_item_class("#f0d060", "DIF"), "macd_dif", "macd")
    chart.add_item(_line_item_class("#4a9eff", "DEA"), "macd_dea", "macd")
    chart.add_item(MacdHistItem, "macd_hist", "macd")
