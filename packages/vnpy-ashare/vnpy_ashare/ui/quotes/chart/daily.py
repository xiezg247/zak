"""行情页 K 线图表组件（中文游标 + A 股配色）。"""

from __future__ import annotations

from datetime import datetime

import pyqtgraph as pg
from vnpy.chart import CandleItem, ChartWidget, VolumeItem
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.components.chart_style import apply_ashare_chart_theme, apply_candle_colors
from vnpy_ashare.ui.quotes.chart.ma_line_item import register_ma_items
from vnpy_ashare.ui.quotes.chart.minute_bars import MinuteBarChange, MinuteBarDiff, prepare_chart_bars

MINUTE_BAR_COUNT = 80
DAILY_BAR_COUNT = 120
WATCHLIST_DAILY_DEFAULT_BAR_COUNT = 60
WATCHLIST_DAILY_BAR_PRESETS: tuple[tuple[str, int], ...] = (
    ("10日", 10),
    ("20日", 20),
    ("30日", 30),
    ("60日", 60),
    ("90日", 90),
    ("全部", DAILY_BAR_COUNT),
)


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


REF_BUY_LINE_COLOR = "#3ddc84"
REF_SELL_LINE_COLOR = "#ff5c5c"
REF_LAST_PRICE_LINE_COLOR = "#ffb020"
ACTION_BUY_LINE_COLOR = "#3ddc8466"
ACTION_SELL_LINE_COLOR = "#ff5c5c66"


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
        self._ref_buy_line: pg.InfiniteLine | None = None
        self._ref_sell_line: pg.InfiniteLine | None = None
        self._ref_last_price_line: pg.InfiniteLine | None = None
        self._action_buy_line: pg.InfiniteLine | None = None
        self._action_sell_line: pg.InfiniteLine | None = None

    def clear_reference_lines(self) -> None:
        plot = self._plots.get("candle")
        if plot is None:
            return
        for attr in (
            "_ref_buy_line",
            "_ref_sell_line",
            "_ref_last_price_line",
            "_action_buy_line",
            "_action_sell_line",
        ):
            line = getattr(self, attr, None)
            if line is not None:
                plot.removeItem(line)
                setattr(self, attr, None)

    def set_reference_lines(
        self,
        *,
        ref_buy: float | None = None,
        ref_sell: float | None = None,
        last_price: float | None = None,
        action_buy: float | None = None,
        action_sell: float | None = None,
    ) -> None:
        """日 K 叠加结构锚点、动作参考价与现价水平线。"""
        plot = self._plots.get("candle")
        if plot is None:
            return
        self.clear_reference_lines()
        dash = QtCore.Qt.PenStyle.DashLine
        dot = QtCore.Qt.PenStyle.DotLine
        if ref_buy is not None and ref_buy > 0:
            self._ref_buy_line = pg.InfiniteLine(
                angle=0,
                pos=ref_buy,
                pen=pg.mkPen(REF_BUY_LINE_COLOR, width=1, style=dash),
            )
            plot.addItem(self._ref_buy_line)
        if ref_sell is not None and ref_sell > 0:
            self._ref_sell_line = pg.InfiniteLine(
                angle=0,
                pos=ref_sell,
                pen=pg.mkPen(REF_SELL_LINE_COLOR, width=1, style=dash),
            )
            plot.addItem(self._ref_sell_line)
        if action_buy is not None and action_buy > 0:
            self._action_buy_line = pg.InfiniteLine(
                angle=0,
                pos=action_buy,
                pen=pg.mkPen(ACTION_BUY_LINE_COLOR, width=1, style=dot),
            )
            plot.addItem(self._action_buy_line)
        if action_sell is not None and action_sell > 0:
            self._action_sell_line = pg.InfiniteLine(
                angle=0,
                pos=action_sell,
                pen=pg.mkPen(ACTION_SELL_LINE_COLOR, width=1, style=dot),
            )
            plot.addItem(self._action_sell_line)
        if last_price is not None and last_price > 0:
            self._ref_last_price_line = pg.InfiniteLine(
                angle=0,
                pos=last_price,
                pen=pg.mkPen(REF_LAST_PRICE_LINE_COLOR, width=1, style=dash),
            )
            plot.addItem(self._ref_last_price_line)

    def configure_scope(self, *, minute: bool) -> None:
        """按日 K / 分 K 调整默认可见根数。"""
        self._default_bar_count = MINUTE_BAR_COUNT if minute else DAILY_BAR_COUNT

    def reset_viewport(self) -> None:
        self._bar_count = self._default_bar_count
        self._right_ix = 0
        if self._cursor:
            self._cursor.clear_all()

    def set_viewport_bar_count(self, bar_count: int) -> None:
        """调整可见 K 线根数（不重新加载数据）。"""
        self._default_bar_count = max(1, int(bar_count))
        self._bar_count = self._default_bar_count
        if self._manager.get_count() <= 0:
            return
        self._sync_viewport_to_data()
        self._sync_cursor_to_last()
        if self.scene():
            self.scene().update()

    def _visible_ix_range(self) -> tuple[int, int]:
        count = self._manager.get_count()
        if count <= 0:
            return 0, 1
        max_ix = min(int(self._right_ix), count)
        min_ix = max(0, max_ix - int(self._bar_count))
        if min_ix >= max_ix:
            min_ix = max(0, max_ix - 1)
        return min_ix, max_ix

    def _update_plot_limits(self) -> None:
        """同一子图合并 K 线与均线上下界，避免 setLimits 被 MA 单独压扁。"""
        count = self._manager.get_count()
        merged: dict[pg.PlotItem, tuple[float, float]] = {}
        for item, plot in self._item_plot_map.items():
            y_min, y_max = item.get_y_range()
            if plot not in merged:
                merged[plot] = (y_min, y_max)
                continue
            prev_min, prev_max = merged[plot]
            merged[plot] = (min(prev_min, y_min), max(prev_max, y_max))

        for plot, (y_min, y_max) in merged.items():
            plot.setLimits(
                xMin=-1,
                xMax=count,
                yMin=y_min,
                yMax=y_max,
            )

    def _update_x_range(self) -> None:
        min_ix, max_ix = self._visible_ix_range()
        for plot in self._plots.values():
            plot.setRange(xRange=(min_ix, max_ix), padding=0)

    def _update_y_range(self) -> None:
        """合并同一子图内 K 线与均线的 Y 范围，避免短视口下 MA 压扁蜡烛。"""
        if not self._first_plot:
            return
        min_ix, max_ix = self._visible_ix_range()
        if min_ix >= max_ix:
            return

        merged: dict[pg.PlotItem, tuple[float, float]] = {}
        for item, plot in self._item_plot_map.items():
            y_min, y_max = item.get_y_range(min_ix, max_ix)
            if plot not in merged:
                merged[plot] = (y_min, y_max)
                continue
            prev_min, prev_max = merged[plot]
            merged[plot] = (min(prev_min, y_min), max(prev_max, y_max))

        for plot, (y_min, y_max) in merged.items():
            span = y_max - y_min
            padding = span * 0.06 if span > 0 else max(abs(y_max) * 0.06, 0.5)
            plot.setRange(yRange=(y_min - padding, y_max + padding))

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

    def apply_bars(self, change: MinuteBarChange) -> None:
        """按 diff 增量或全量更新 K 线，减少定时刷新闪烁。"""
        if change.diff == MinuteBarDiff.NOOP:
            return
        if change.diff == MinuteBarDiff.REPLACE or self._manager.get_count() <= 0:
            self.replace_history(change.bars)
            return

        bars = prepare_chart_bars(change.bars)
        if not bars:
            self.replace_history([])
            return

        old_count = self._manager.get_count()
        was_at_right = self._right_ix >= max(old_count - 1, 0)

        self.setUpdatesEnabled(False)
        try:
            for bar in bars[change.patch_from :]:
                self._manager.update_bar(bar)
                for item in self._items.values():
                    item.update_bar(bar)
            self._update_plot_limits()
            if was_at_right:
                self._right_ix = len(bars)
                self._update_x_range()
            self._update_y_range()
            if was_at_right:
                self._sync_cursor_to_last()
        finally:
            self.setUpdatesEnabled(True)
            if self.scene():
                self.scene().update()

    def replace_history(self, history: list[BarData]) -> None:
        """全量替换 K 线，避免 BarManager 按 datetime 合并旧周期。"""
        self.clear_reference_lines()
        history = prepare_chart_bars(history)
        self.setUpdatesEnabled(False)
        try:
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
        finally:
            self.setUpdatesEnabled(True)
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
                    self._right_ix = min(max(0, int(max_x)), count)
                    self._update_y_range()
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
    bar_count = MINUTE_BAR_COUNT if minute else WATCHLIST_DAILY_DEFAULT_BAR_COUNT
    return _create_ashare_kline_chart(bar_count=bar_count)
