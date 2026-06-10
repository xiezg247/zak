"""行情页图表深色主题（市场 / 自选 / 本地共用）。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.chart import ChartWidget
from vnpy.trader.ui import QtGui

from vnpy_ashare.ui.styles import FALL_COLOR, RISE_COLOR
from vnpy_ashare.ui.theme.build_chart import (
    AVG_LINE_COLOR,
    CHART_BG,
    CHART_FRAME_STYLESHEET,
    CHART_PANEL_BG,
    CHART_PANEL_STYLESHEET,
    GRID_ALPHA,
    INTRADAY_AVG_LINE_WIDTH,
    INTRADAY_CROSSHAIR_COLOR,
    INTRADAY_INFO_COLOR,
    INTRADAY_INFO_STYLESHEET,
    INTRADAY_LAST_DOT_SIZE,
    INTRADAY_LUNCH_LINE_COLOR,
    INTRADAY_PRICE_LINE_WIDTH,
    PREV_CLOSE_COLOR,
    ChartPalette,
    AXIS_COLOR,
    AXIS_TEXT_COLOR,
    build_chart_frame_stylesheet,
    build_chart_panel_stylesheet,
    build_intraday_info_stylesheet,
    chart_palette,
)
from vnpy_ashare.ui.theme.tokens import ThemeTokens

__all__ = [
    "AVG_LINE_COLOR",
    "AXIS_COLOR",
    "AXIS_TEXT_COLOR",
    "CHART_BG",
    "CHART_FRAME_STYLESHEET",
    "CHART_PANEL_BG",
    "CHART_PANEL_STYLESHEET",
    "ChartPalette",
    "GRID_ALPHA",
    "INTRADAY_AVG_LINE_WIDTH",
    "INTRADAY_CROSSHAIR_COLOR",
    "INTRADAY_INFO_COLOR",
    "INTRADAY_INFO_STYLESHEET",
    "INTRADAY_LAST_DOT_SIZE",
    "INTRADAY_LUNCH_LINE_COLOR",
    "INTRADAY_PRICE_LINE_WIDTH",
    "PREV_CLOSE_COLOR",
    "RISE_RGB",
    "FALL_RGB",
    "apply_ashare_chart_theme",
    "apply_candle_colors",
    "build_chart_frame_stylesheet",
    "build_chart_panel_stylesheet",
    "build_intraday_info_stylesheet",
    "chart_palette",
    "style_intraday_price_plot",
    "style_intraday_volume_plot",
]


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


def apply_ashare_chart_theme(chart: ChartWidget, tokens: ThemeTokens | None = None) -> None:
    from vnpy_ashare.ui.theme import theme_manager

    manager = theme_manager()
    if tokens is None:
        tokens = manager.tokens()
    palette = chart_palette(tokens)
    _apply_chart_theme(chart, palette)
    manager.register_chart(chart)


def _apply_chart_theme(chart: ChartWidget, palette: ChartPalette) -> None:
    chart.setBackground(palette.bg)
    chart._layout.setBorder(color=palette.border, width=0.6)

    for plot in chart.get_all_plots():
        view = plot.getViewBox()
        view.setBackgroundColor(pg.mkColor(palette.bg))
        plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)

        for axis_name in ("right", "bottom"):
            axis = plot.getAxis(axis_name)
            if axis is None:
                continue
            axis.setPen(pg.mkPen(palette.axis_color))
            axis.setTextPen(pg.mkPen(palette.axis_text))


def _style_plot_axes(plot: pg.PlotItem, palette: ChartPalette, *, sides: tuple[str, ...]) -> None:
    plot.setMenuEnabled(False)
    plot.getViewBox().setMouseEnabled(x=False, y=False)
    for side in ("left", "right", "bottom"):
        if side in sides:
            plot.showAxis(side)
            axis = plot.getAxis(side)
            axis.setPen(pg.mkPen(palette.axis_color))
            axis.setTextPen(pg.mkPen(palette.axis_text))
            if side == "left":
                axis.setWidth(52)
            elif side == "right":
                axis.setWidth(48)
        else:
            plot.hideAxis(side)


def style_intraday_price_plot(plot: pg.PlotItem, palette: ChartPalette | None = None) -> None:
    if palette is None:
        from vnpy_ashare.ui.theme import theme_manager

        palette = chart_palette(theme_manager().tokens())
    plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    plot.setLabel("left", "")
    plot.setLabel("right", "")
    _style_plot_axes(plot, palette, sides=("left", "right"))


def style_intraday_volume_plot(plot: pg.PlotItem, palette: ChartPalette | None = None) -> None:
    if palette is None:
        from vnpy_ashare.ui.theme import theme_manager

        palette = chart_palette(theme_manager().tokens())
    plot.showGrid(x=False, y=True, alpha=0.08)
    plot.setLabel("left", "")
    plot.setMaximumHeight(96)
    _style_plot_axes(plot, palette, sides=("left", "bottom"))
