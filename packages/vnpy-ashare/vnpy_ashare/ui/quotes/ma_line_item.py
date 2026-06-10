"""K 线均线叠加。"""

from __future__ import annotations

import math

import pyqtgraph as pg
from vnpy.chart.item import ChartItem
from vnpy.chart.manager import BarManager
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtGui

MA_LINE_SPECS: tuple[tuple[int, str, str], ...] = (
    (5, "#f0d060", "MA5"),
    (10, "#4a9eff", "MA10"),
    (20, "#d45bff", "MA20"),
)


def calc_sma(bars: list[BarData], period: int) -> list[float]:
    values: list[float] = []
    for index in range(len(bars)):
        if index + 1 < period:
            values.append(math.nan)
            continue
        window = bars[index - period + 1 : index + 1]
        values.append(sum(bar.close_price for bar in window) / period)
    return values


class MaLineItem(ChartItem):
    """简单移动平均线。"""

    def __init__(
        self,
        manager: BarManager,
        period: int,
        color: str,
        label: str,
    ) -> None:
        super().__init__(manager)
        self._period = period
        self._label = label
        self._pen = pg.mkPen(color=color, width=1)
        self._values: list[float] = []

    def _rebuild_values(self) -> None:
        self._values = calc_sma(self._manager.get_all_bars(), self._period)

    def update_history(self, history: list[BarData]) -> None:
        super().update_history(history)
        self._rebuild_values()

    def update_bar(self, bar: BarData) -> None:
        super().update_bar(bar)
        self._rebuild_values()

    def clear_all(self) -> None:
        super().clear_all()
        self._values = []

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        picture = QtGui.QPicture()
        return picture

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
            return QtCore.QRectF(0.0, 0.0, 0.0, 0.0)
        min_price, max_price = self._manager.get_price_range()
        height = max_price - min_price
        if height <= 0:
            height = 1.0
        return QtCore.QRectF(0.0, min_price, float(count), height)

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
            return 0.0, 1.0
        return min(valid), max(valid)

    def get_info_text(self, ix: int) -> str:
        if ix < 0 or ix >= len(self._values):
            return ""
        value = self._values[ix]
        if math.isnan(value):
            return ""
        return f"{self._label} {value:.2f}"


def ma_line_item_class(period: int, color: str, label: str) -> type[MaLineItem]:
    """生成 vnpy ChartWidget.add_item 可用的均线类。"""

    class _MaLineItem(MaLineItem):
        def __init__(self, manager: BarManager) -> None:
            super().__init__(manager, period, color, label)

    _MaLineItem.__name__ = f"Ma{period}LineItem"
    _MaLineItem.__qualname__ = f"Ma{period}LineItem"
    return _MaLineItem


def register_ma_items(chart: object, specs: tuple[tuple[int, str, str], ...] = MA_LINE_SPECS) -> None:
    for period, color, label in specs:
        item_class = ma_line_item_class(period, color, label)
        chart.add_item(item_class, f"ma{period}", "candle")
