"""回测结果图表：兼容 pandas 2.x + pyqtgraph，并接入终端主题。"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pandas import DataFrame
from vnpy_ctabacktester.ui.widget import BacktesterChart, StatisticsMonitor

from vnpy_ashare.ui.chart_style import GRID_ALPHA
from vnpy_ashare.ui.theme import theme_manager
from vnpy_ashare.ui.theme.build_chart import ChartPalette, chart_palette
from vnpy_ashare.ui.theme.tokens import ThemeTokens


def _style_backtest_plot(plot: pg.PlotItem, palette: ChartPalette) -> None:
    plot.setMenuEnabled(False)
    plot.getViewBox().setBackgroundColor(pg.mkColor(palette.panel_bg))
    plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    for axis_name in ("left", "bottom", "right", "top"):
        axis = plot.getAxis(axis_name)
        if axis is None:
            continue
        axis.setPen(pg.mkPen(palette.axis_color))
        axis.setTextPen(pg.mkPen(palette.axis_text))
    title = getattr(plot, "titleLabel", None)
    if title is not None:
        plot.setTitle(color=palette.axis_text)


def apply_backtest_chart_theme(chart: BacktesterChart, *, tokens: ThemeTokens | None = None) -> None:
    palette = chart_palette(tokens or theme_manager().tokens())
    chart.setBackground(palette.panel_bg)
    for attr in ("balance_plot", "drawdown_plot", "pnl_plot", "distribution_plot"):
        plot = getattr(chart, attr, None)
        if plot is not None:
            _style_backtest_plot(plot, palette)


class AshareStatisticsMonitor(StatisticsMonitor):
    """回测统计表：随主题刷新样式。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BacktestStatisticsTable")
        self.setAlternatingRowColors(True)
        theme_manager().register_callback(self._on_theme_changed)

    def _on_theme_changed(self, _tokens: ThemeTokens) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        header = self.verticalHeader()
        header.style().unpolish(header)
        header.style().polish(header)


class AshareBacktesterChart(BacktesterChart):
    """
    vnpy 原实现将 df['balance'] 直接传给 pyqtgraph，在 DatetimeIndex 下会 KeyError: 0。
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BacktesterChart")
        theme_manager().register_callback(self._on_theme_changed)
        apply_backtest_chart_theme(self)

    def _on_theme_changed(self, tokens: ThemeTokens) -> None:
        apply_backtest_chart_theme(self, tokens=tokens)

    def set_data(self, df: DataFrame) -> None:
        if df is None:
            return

        self.dates.clear()
        for n, date in enumerate(df.index):
            self.dates[n] = date

        balance = df["balance"].to_numpy()
        drawdown = df["drawdown"].to_numpy()
        net_pnl = df["net_pnl"].to_numpy()

        self.balance_curve.setData(balance)
        self.drawdown_curve.setData(drawdown)

        profit_pnl_x: list[int] = []
        profit_pnl_height: list[float] = []
        loss_pnl_x: list[int] = []
        loss_pnl_height: list[float] = []

        for count, pnl in enumerate(net_pnl):
            if pnl >= 0:
                profit_pnl_height.append(float(pnl))
                profit_pnl_x.append(count)
            else:
                loss_pnl_height.append(float(pnl))
                loss_pnl_x.append(count)

        self.profit_pnl_bar.setOpts(x=profit_pnl_x, height=profit_pnl_height)
        self.loss_pnl_bar.setOpts(x=loss_pnl_x, height=loss_pnl_height)

        hist, x = np.histogram(net_pnl, bins="auto")
        x = x[:-1]
        self.distribution_curve.setData(x, hist)
