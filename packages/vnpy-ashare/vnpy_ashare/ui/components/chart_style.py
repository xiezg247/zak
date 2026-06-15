"""行情页图表深色主题（市场 / 自选 / 本地共用）。"""

from __future__ import annotations

from typing import cast

import pyqtgraph as pg
from vnpy.chart import ChartWidget

from vnpy_common.ui.theme.build_chart import (
    AVG_LINE_COLOR,
    AXIS_COLOR,
    AXIS_TEXT_COLOR,
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
    build_chart_frame_stylesheet,
    build_chart_panel_stylesheet,
    build_intraday_info_stylesheet,
    chart_palette,
)
from vnpy_common.ui.theme.market_colors import hex_to_rgb, market_rgb
from vnpy_common.ui.theme.tokens import DARK_TOKENS, ThemeTokens

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
    "apply_sparkline_plot_theme",
    "build_chart_frame_stylesheet",
    "build_chart_panel_stylesheet",
    "build_intraday_info_stylesheet",
    "chart_palette",
    "hex_to_rgb",
    "style_intraday_price_plot",
    "style_intraday_volume_plot",
]


RISE_RGB = hex_to_rgb(DARK_TOKENS.market_rise)
FALL_RGB = hex_to_rgb(DARK_TOKENS.market_fall)


def apply_candle_colors(item: object, *, tokens: ThemeTokens | None = None) -> None:
    """A 股红涨绿跌实心 K 线。"""
    from vnpy_common.ui.theme import theme_manager

    if tokens is None:
        tokens = theme_manager().tokens()
    rise_rgb, fall_rgb = market_rgb(tokens)
    item._up_pen = pg.mkPen(color=rise_rgb, width=1)
    item._up_brush = pg.mkBrush(color=rise_rgb)
    item._down_pen = pg.mkPen(color=fall_rgb, width=1)
    item._down_brush = pg.mkBrush(color=fall_rgb)
    item._black_brush = item._up_brush


def apply_sparkline_plot_theme(plot: pg.PlotWidget, tokens: ThemeTokens | None = None) -> None:
    """轻量折线/迷你图主题（普通 PlotWidget，非 vnpy ChartWidget）。"""
    from vnpy_common.ui.theme import theme_manager

    if tokens is None:
        tokens = theme_manager().tokens()
    palette = chart_palette(tokens)
    plot.setBackground(palette.bg)
    item = plot.getPlotItem()
    item.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    view = item.getViewBox()
    view.setBackgroundColor(pg.mkColor(palette.bg))
    view.setMouseEnabled(x=False, y=False)
    for axis_name in ("left", "bottom"):
        axis = item.getAxis(axis_name)
        if axis is None:
            continue
        axis.setPen(pg.mkPen(palette.axis_color))
        axis.setTextPen(pg.mkPen(palette.axis_text))
    item.hideAxis("right")
    item.setMenuEnabled(False)


def apply_ashare_chart_theme(chart: ChartWidget, tokens: ThemeTokens | None = None) -> None:
    from vnpy_common.ui.theme import theme_manager

    manager = theme_manager()
    if tokens is None:
        tokens = manager.tokens()
    palette = chart_palette(tokens)
    _apply_chart_theme(chart, palette)
    for item in getattr(chart, "_items", {}).values():
        if hasattr(item, "_up_pen"):
            apply_candle_colors(item, tokens=tokens)
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
        from vnpy_common.ui.theme import theme_manager

        palette = chart_palette(theme_manager().tokens())
    plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    plot.setLabel("left", "")
    plot.setLabel("right", "")
    _style_plot_axes(plot, palette, sides=("left", "right"))


def style_intraday_volume_plot(plot: pg.PlotItem, palette: ChartPalette | None = None) -> None:
    if palette is None:
        from vnpy_common.ui.theme import theme_manager

        palette = chart_palette(theme_manager().tokens())
    plot.showGrid(x=False, y=True, alpha=0.08)
    plot.setLabel("left", "")
    plot.setMaximumHeight(96)
    _style_plot_axes(plot, palette, sides=("left", "bottom"))


def refresh_charts_for_theme(tokens: ThemeTokens, charts: list[object]) -> None:
    """ThemeManager 回调：刷新已注册图表配色。"""
    palette = chart_palette(tokens)
    for chart in charts:
        _apply_chart_theme(cast(ChartWidget, chart), palette)
        for item in getattr(chart, "_items", {}).values():
            if hasattr(item, "_up_pen"):
                apply_candle_colors(item, tokens=tokens)
