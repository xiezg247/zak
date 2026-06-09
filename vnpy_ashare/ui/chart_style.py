"""行情页图表深色主题（市场 / 自选 / 本地共用）。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.chart import ChartWidget
from vnpy.trader.ui import QtGui

from vnpy_ashare.ui.styles import FALL_COLOR, RISE_COLOR

CHART_BG = "#1a1a1a"
CHART_PANEL_BG = "#141414"
GRID_ALPHA = 0.12
AXIS_COLOR = "#666666"
AXIS_TEXT_COLOR = "#a0a0a0"
AVG_LINE_COLOR = "#e6b422"
PREV_CLOSE_COLOR = "#888888"
INTRADAY_CROSSHAIR_COLOR = "#5a5a5a"
INTRADAY_LUNCH_LINE_COLOR = "#333333"
INTRADAY_INFO_COLOR = "#9a9a9a"
INTRADAY_LAST_DOT_SIZE = 7
INTRADAY_PRICE_LINE_WIDTH = 2.0
INTRADAY_AVG_LINE_WIDTH = 1.2

INTRADAY_INFO_STYLESHEET = """
QLabel#IntradayInfoBar {
    color: #9a9a9a;
    font-size: 11px;
    padding: 2px 6px;
    background-color: transparent;
}
"""

CHART_FRAME_STYLESHEET = """
QWidget#ChartFrame {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
}
QLabel#ChartHint {
    color: #6a6a6a;
    font-size: 13px;
}
QWidget#MaLegendBar {
    background-color: #1a1a1a;
    border-bottom: 1px solid #252525;
    font-size: 11px;
}
"""

CHART_PANEL_STYLESHEET = (
    CHART_FRAME_STYLESHEET
    + """
QWidget#ChartPanel {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #1e1e1e;
    color: #8a8a8a;
    border: 1px solid #2a2a2a;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 14px;
    margin-right: 2px;
    font-size: 12px;
}
QTabBar::tab:selected {
    background-color: #1a1a1a;
    color: #e8e8e8;
    border-color: #3a3a3a;
}
QTabBar::tab:hover {
    color: #c8c8c8;
}
QComboBox {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    color: #d0d0d0;
    padding: 3px 8px;
    font-size: 12px;
    min-width: 56px;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox QAbstractItemView {
    background-color: #252525;
    color: #d0d0d0;
    selection-background-color: #333333;
    border: 1px solid #3a3a3a;
}
"""
)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = QtGui.QColor(hex_color)
    return color.red(), color.green(), color.blue()


RISE_RGB = hex_to_rgb(RISE_COLOR)
FALL_RGB = hex_to_rgb(FALL_COLOR)


def apply_candle_colors(item: object) -> None:
    """A 股红涨绿跌实心 K 线。"""
    item._up_pen = pg.mkPen(color=RISE_RGB, width=1)
    item._up_brush = pg.mkBrush(color=RISE_RGB)
    item._down_pen = pg.mkPen(color=FALL_RGB, width=1)
    item._down_brush = pg.mkBrush(color=FALL_RGB)
    item._black_brush = item._up_brush


def apply_ashare_chart_theme(chart: ChartWidget) -> None:
    chart.setBackground(CHART_BG)
    chart._layout.setBorder(color="#2a2a2a", width=0.6)

    for plot in chart.get_all_plots():
        view = plot.getViewBox()
        view.setBackgroundColor(pg.mkColor(CHART_BG))
        plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)

        for axis_name in ("right", "bottom"):
            axis = plot.getAxis(axis_name)
            if axis is None:
                continue
            axis.setPen(pg.mkPen(AXIS_COLOR))
            axis.setTextPen(pg.mkPen(AXIS_TEXT_COLOR))


def _style_plot_axes(plot: pg.PlotItem, *, sides: tuple[str, ...]) -> None:
    plot.setMenuEnabled(False)
    plot.getViewBox().setMouseEnabled(x=False, y=False)
    for side in ("left", "right", "bottom"):
        if side in sides:
            plot.showAxis(side)
            axis = plot.getAxis(side)
            axis.setPen(pg.mkPen(AXIS_COLOR))
            axis.setTextPen(pg.mkPen(AXIS_TEXT_COLOR))
            if side == "left":
                axis.setWidth(52)
            elif side == "right":
                axis.setWidth(48)
        else:
            plot.hideAxis(side)


def style_intraday_price_plot(plot: pg.PlotItem) -> None:
    plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    plot.setLabel("left", "")
    plot.setLabel("right", "")
    _style_plot_axes(plot, sides=("left", "right"))


def style_intraday_volume_plot(plot: pg.PlotItem) -> None:
    plot.showGrid(x=False, y=True, alpha=0.08)
    plot.setLabel("left", "")
    plot.setMaximumHeight(96)
    _style_plot_axes(plot, sides=("left", "bottom"))
