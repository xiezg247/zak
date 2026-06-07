"""行情页 K 线图表组件（中文游标 + A 股配色）。"""

from __future__ import annotations

from datetime import datetime

import pyqtgraph as pg
from vnpy.chart import CandleItem, ChartWidget, VolumeItem
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtGui, QtWidgets

from vnpy_ashare.ui.chart_style import apply_ashare_chart_theme, apply_candle_colors
from vnpy_ashare.ui.ma_line_item import register_ma_items

MINUTE_BAR_COUNT = 80
DAILY_BAR_COUNT = 120


def prepare_chart_bars(bars: list[BarData]) -> list[BarData]:
    """排序并去重，避免 BarManager 按 datetime 合并时索引错位。"""
    if not bars:
        return []
    unique: dict[datetime, BarData] = {}
    for bar in bars:
        unique[bar.datetime] = bar
    return [unique[dt] for dt in sorted(unique.keys())]


class ChineseCandleItem(CandleItem):
    """K 线游标：中文 OHLC 标签。"""

    def get_info_text(self, ix: int) -> str:
        bar: BarData | None = self._manager.get_bar(ix)
        if not bar:
            return ""

        words: list[str] = [
            "日期",
            bar.datetime.strftime("%Y-%m-%d"),
        ]
        if bar.datetime.hour or bar.datetime.minute or bar.datetime.second:
            words.extend(["", "时间", bar.datetime.strftime("%H:%M:%S")])

        words.extend(
            [
                "",
                "开盘",
                f"{bar.open_price:.2f}",
                "",
                "最高",
                f"{bar.high_price:.2f}",
                "",
                "最低",
                f"{bar.low_price:.2f}",
                "",
                "收盘",
                f"{bar.close_price:.2f}",
            ]
        )
        return "\n".join(words)


class ChineseVolumeItem(VolumeItem):
    """成交量游标：中文标签。"""

    def get_info_text(self, ix: int) -> str:
        bar: BarData | None = self._manager.get_bar(ix)
        if not bar:
            return ""
        return f"成交量 {bar.volume:.0f}"


class AshareCandleItem(ChineseCandleItem):
    """A 股实心 K 线。"""

    def __init__(self, manager: object) -> None:
        super().__init__(manager)
        apply_candle_colors(self)


class AshareVolumeItem(ChineseVolumeItem):
    """A 股配色成交量柱。"""

    def __init__(self, manager: object) -> None:
        super().__init__(manager)
        apply_candle_colors(self)


class AshareChartWidget(ChartWidget):
    """A 股 K 线图：切换周期时重置视口，避免坐标与数据错位。"""

    def __init__(
        self,
        *,
        bar_count: int = DAILY_BAR_COUNT,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._default_bar_count = bar_count
        self._bar_count = bar_count

    def configure_scope(self, *, minute: bool) -> None:
        """按日 K / 分 K 调整默认可见根数。"""
        self._default_bar_count = MINUTE_BAR_COUNT if minute else DAILY_BAR_COUNT

    def reset_viewport(self) -> None:
        self._bar_count = self._default_bar_count
        self._right_ix = 0
        if self._cursor:
            self._cursor.clear_all()

    def _sync_viewport_to_data(self) -> None:
        """将视口与当前 K 线数量对齐，避免切换标的后沿用旧坐标范围。"""
        count = self._manager.get_count()
        if count <= 0:
            self._force_x_range_update()
            return
        self._right_ix = count
        self._update_x_range()
        self._update_y_range()

    def update_history(self, history: list[BarData]) -> None:
        """禁止合并写入：1 分与 5/15/30/60 分共享时间戳时合并会导致索引错位。"""
        self.replace_history(history)

    def replace_history(self, history: list[BarData]) -> None:
        """全量替换 K 线，避免 BarManager 按 datetime 合并旧周期。"""
        history = prepare_chart_bars(history)
        self._manager.clear_all()
        for item in self._items.values():
            item.clear_all()
        if self._cursor:
            self._cursor.clear_all()
        self.reset_viewport()
        if not history:
            self._force_x_range_update()
            return

        self._manager.update_history(history)
        for item in self._items.values():
            item.update_history(history)
        self._update_plot_limits()
        self._sync_viewport_to_data()
        self._sync_cursor_to_last()
        if self.scene():
            self.scene().update()

    def _force_x_range_update(self) -> None:
        count = self._manager.get_count()
        self._right_ix = count
        for plot in self._plots.values():
            plot.setRange(xRange=(0, max(count, 1)), padding=0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        if self._first_plot:
            count = self._manager.get_count()
            if count > 0:
                view = self._first_plot.getViewBox()
                min_x, max_x = view.viewRange()[0]
                if max_x > count + 1 or min_x >= count:
                    self._sync_viewport_to_data()
                else:
                    self._right_ix = min(max(0, max_x), count)
            else:
                self._right_ix = 0
        pg.PlotWidget.paintEvent(self, event)

    def _sync_cursor_to_last(self) -> None:
        if self._cursor is None:
            return
        count = self._manager.get_count()
        if count <= 0:
            return
        last_ix = count - 1
        bar = self._manager.get_bar(last_ix)
        if bar is None:
            return
        self._cursor._x = last_ix
        self._cursor._y = bar.close_price
        self._cursor._update_line()
        self._cursor._update_label()
        self._cursor.update_info()


def _create_ashare_kline_chart(*, bar_count: int = DAILY_BAR_COUNT) -> AshareChartWidget:
    chart = AshareChartWidget(bar_count=bar_count)
    chart.add_plot("candle", hide_x_axis=True, minimum_height=200)
    chart.add_plot("volume", maximum_height=120, minimum_height=60)
    chart.add_item(AshareCandleItem, "candle", "candle")
    register_ma_items(chart)
    chart.add_item(AshareVolumeItem, "volume", "volume")
    chart.add_cursor()
    apply_ashare_chart_theme(chart)
    return chart


def create_daily_chart() -> AshareChartWidget:
    """市场 / 本地页日 K。"""
    return _create_ashare_kline_chart(bar_count=DAILY_BAR_COUNT)


def create_watchlist_chart(*, minute: bool = False) -> AshareChartWidget:
    """自选页日 K / 分 K。"""
    return _create_ashare_kline_chart(bar_count=MINUTE_BAR_COUNT if minute else DAILY_BAR_COUNT)
