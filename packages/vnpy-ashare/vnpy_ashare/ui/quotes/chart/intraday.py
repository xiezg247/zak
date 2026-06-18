"""日内分时折线图。"""

from __future__ import annotations

import bisect

import pyqtgraph as pg
from vnpy.trader.object import BarData
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.time.market_hours import (
    INTRADAY_SESSION_MINUTES,
    MORNING_SESSION_MINUTES,
    bar_session_minute,
    intraday_axis_ticks,
    vwap_price,
)
from vnpy_ashare.ui.components.chart_style import (
    AVG_LINE_COLOR,
    INTRADAY_AVG_LINE_WIDTH,
    INTRADAY_LAST_DOT_SIZE,
    INTRADAY_PRICE_LINE_WIDTH,
    PREV_CLOSE_COLOR,
    build_intraday_info_stylesheet,
    chart_palette,
    style_intraday_price_plot,
    style_intraday_volume_plot,
)
from vnpy_common.ui.theme.html_palette import html_palette
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors, market_rgb, price_change_color
from vnpy_common.ui.theme.tokens import ThemeTokens

VOLUME_BAR_WIDTH = 0.75
PRICE_ROW_STRETCH = 3
VOLUME_ROW_STRETCH = 1


class PercentChangeAxis(pg.AxisItem):
    """右侧涨跌幅刻度（与左侧价格共用 Y 坐标）。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._prev_close = 0.0

    def set_prev_close(self, prev_close: float) -> None:
        self._prev_close = prev_close

    def tickStrings(self, values, scale, spacing) -> list[str]:
        if self._prev_close <= 0:
            return ["" for _ in values]
        return [format_pct_tick(value, self._prev_close) for value in values]


def calc_intraday_avg_prices(bars: list[BarData]) -> list[float]:
    """按累计成交额 / 成交量（手）计算分时均价。"""
    cumulative_amount = 0.0
    cumulative_lots = 0.0
    avg_prices: list[float] = []
    for bar in bars:
        cumulative_amount += bar.turnover
        cumulative_lots += bar.volume
        if cumulative_lots > 0:
            avg_prices.append(vwap_price(cumulative_amount, cumulative_lots))
        else:
            avg_prices.append(bar.close_price)
    return avg_prices


def session_x_values(bars: list[BarData]) -> list[float]:
    return [bar_session_minute(bar.datetime) for bar in bars]


def price_y_range(
    prices: list[float],
    *,
    prev_close: float = 0.0,
    padding_ratio: float = 0.06,
) -> tuple[float, float]:
    values = list(prices)
    if prev_close > 0:
        values.append(prev_close)
    low = min(values)
    high = max(values)
    span = high - low
    padding = span * padding_ratio if span > 0 else max(abs(high) * padding_ratio, 0.5)
    return low - padding, high + padding


def volume_y_range(volumes: list[float]) -> tuple[float, float]:
    if not volumes:
        return 0.0, 1.0
    peak = max(volumes)
    return 0.0, peak * 1.12 if peak > 0 else 1.0


def nearest_bar_index(xs: list[float], x: float) -> int | None:
    """按交易分钟坐标吸附最近一根 bar。"""
    if not xs:
        return None
    pos = bisect.bisect_left(xs, x)
    if pos <= 0:
        return 0
    if pos >= len(xs):
        return len(xs) - 1
    before = pos - 1
    if abs(xs[before] - x) <= abs(xs[pos] - x):
        return before
    return pos


def pct_change(price: float, prev_close: float) -> float:
    if prev_close <= 0:
        return 0.0
    return (price - prev_close) / prev_close * 100


def format_pct_tick(price: float, prev_close: float) -> str:
    if prev_close <= 0:
        return ""
    return f"{pct_change(price, prev_close):+.2f}%"


def change_color(price: float, prev_close: float, *, tokens: ThemeTokens | None = None) -> str:
    if tokens is None:
        tokens = theme_manager().tokens()
    return price_change_color(price, prev_close, tokens)


def format_change(price: float, prev_close: float) -> tuple[str, str]:
    if prev_close <= 0:
        return "—", "—"
    delta = price - prev_close
    pct = pct_change(price, prev_close)
    return f"{delta:+.2f}", f"{pct:+.2f}%"


def volume_bar_color(bar: BarData, *, tokens: ThemeTokens | None = None) -> tuple[int, int, int]:
    """A 股分钟量柱：收涨红、收跌绿。"""
    if tokens is None:
        tokens = theme_manager().tokens()
    rise_rgb, fall_rgb = market_rgb(tokens)
    if bar.close_price >= bar.open_price:
        return rise_rgb
    return fall_rgb


def _interp_cross_x(x0: float, y0: float, x1: float, y1: float, y_target: float) -> float:
    if y1 == y0:
        return x1
    ratio = (y_target - y0) / (y1 - y0)
    return x0 + ratio * (x1 - x0)


def build_price_segments(
    xs: list[float],
    prices: list[float],
    prev_close: float,
) -> list[tuple[list[float], list[float], bool]]:
    """按昨收分割涨跌区间，供双色价格线使用。"""
    if not xs or prev_close <= 0 or len(xs) != len(prices):
        return []

    segments: list[tuple[list[float], list[float], bool]] = []
    seg_x = [xs[0]]
    seg_y = [prices[0]]
    rising = prices[0] >= prev_close

    def is_rising(price: float) -> bool:
        return price >= prev_close

    for index in range(1, len(xs)):
        x0, y0 = xs[index - 1], prices[index - 1]
        x1, y1 = xs[index], prices[index]
        if is_rising(y0) == is_rising(y1):
            seg_x.append(x1)
            seg_y.append(y1)
            continue
        cross_x = _interp_cross_x(x0, y0, x1, y1, prev_close)
        seg_x.append(cross_x)
        seg_y.append(prev_close)
        if len(seg_x) >= 2:
            segments.append((seg_x, seg_y, rising))
        rising = is_rising(y1)
        seg_x = [cross_x, x1]
        seg_y = [prev_close, y1]

    if len(seg_x) >= 2:
        segments.append((seg_x, seg_y, rising))
    return segments


def format_volume_lots(volume: float) -> str:
    if volume <= 0:
        return "—"
    if volume >= 1e4:
        return f"{volume / 1e4:.2f}万手"
    return f"{volume:.0f}手"


def format_intraday_summary(
    bar: BarData,
    *,
    avg_price: float,
    prev_close: float,
    tokens: ThemeTokens | None = None,
) -> str:
    """顶部信息栏文案。"""

    colors = html_palette(tokens or theme_manager().tokens())
    time_label = bar.datetime.strftime("%H:%M")
    delta_text, pct_text = format_change(bar.close_price, prev_close)
    label = colors.label
    parts = [
        f"<span style='color:{label}'>时间</span> {time_label}",
        f"<span style='color:{label}'>现价</span> <span style='color:{change_color(bar.close_price, prev_close, tokens=tokens)}'>{bar.close_price:.2f}</span>",
        f"<span style='color:{label}'>均价</span> <span style='color:{AVG_LINE_COLOR}'>{avg_price:.2f}</span>",
        f"<span style='color:{label}'>成交量</span> {format_volume_lots(bar.volume)}",
    ]
    if prev_close > 0:
        color = change_color(bar.close_price, prev_close, tokens=tokens)
        parts.append(f"<span style='color:{label}'>涨跌</span> <span style='color:{color}'>{delta_text} ({pct_text})</span>")
    return "  ·  ".join(parts)


def format_intraday_idle_summary(
    bar: BarData,
    *,
    avg_price: float,
    prev_close: float,
    tokens: ThemeTokens | None = None,
) -> str:
    """无鼠标悬停时展示最新价。"""

    colors = html_palette(tokens or theme_manager().tokens())
    delta_text, pct_text = format_change(bar.close_price, prev_close)
    color = change_color(bar.close_price, prev_close, tokens=tokens)
    text = (
        f"最新 <span style='color:{color}; font-weight:600'>{bar.close_price:.2f}</span>"
        f"  ·  均价 <span style='color:{AVG_LINE_COLOR}'>{avg_price:.2f}</span>"
        f"  ·  量 {format_volume_lots(bar.volume)}"
    )
    if prev_close > 0:
        text += f"  ·  涨跌 <span style='color:{color}'>{delta_text} ({pct_text})</span>"
    text += f"  ·  <span style='color:{colors.hint}'>移动鼠标查看历史分时</span>"
    return text


class IntradayChart(QtWidgets.QWidget):
    """价格线 + 均价线 + 涨跌幅轴 + 成交量副图 + 十字光标。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)

        self._bars: list[BarData] = []
        self._xs: list[float] = []
        self._prices: list[float] = []
        self._avg_prices: list[float] = []
        self._volumes: list[float] = []
        self._prev_close = 0.0
        self._hover_index: int | None = None

        self._info_bar = QtWidgets.QLabel("—")
        self._info_bar.setObjectName("IntradayInfoBar")
        self._info_bar.setTextFormat(QtCore.Qt.TextFormat.RichText)
        theme_manager().bind_stylesheet(self._info_bar, extra=build_intraday_info_stylesheet)

        self._gfx = pg.GraphicsLayoutWidget()
        self._palette = chart_palette(theme_manager().tokens())
        self._gfx.setBackground(self._palette.bg)

        self._pct_axis = PercentChangeAxis(orientation="right")
        self._price_plot = self._gfx.addPlot(
            row=0,
            col=0,
            axisItems={"right": self._pct_axis},
        )
        self._volume_plot = self._gfx.addPlot(row=1, col=0)
        self._volume_plot.setXLink(self._price_plot)
        self._gfx.ci.layout.setRowStretchFactor(0, PRICE_ROW_STRETCH)
        self._gfx.ci.layout.setRowStretchFactor(1, VOLUME_ROW_STRETCH)

        style_intraday_price_plot(self._price_plot, self._palette)
        style_intraday_volume_plot(self._volume_plot, self._palette)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._gfx, stretch=1)

        cross_pen = pg.mkPen(self._palette.crosshair, width=1, style=QtCore.Qt.PenStyle.DashLine)
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=cross_pen)
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=cross_pen)
        self._vline_vol = pg.InfiniteLine(angle=90, movable=False, pen=cross_pen)
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self._vline_vol.setVisible(False)
        self._price_plot.addItem(self._vline, ignoreBounds=True)
        self._price_plot.addItem(self._hline, ignoreBounds=True)
        self._volume_plot.addItem(self._vline_vol, ignoreBounds=True)

        for plot in (self._price_plot, self._volume_plot):
            lunch_line = pg.InfiniteLine(
                angle=90,
                pos=float(MORNING_SESSION_MINUTES),
                movable=False,
                pen=pg.mkPen(self._palette.lunch_line, width=1, style=QtCore.Qt.PenStyle.DotLine),
            )
            plot.addItem(lunch_line, ignoreBounds=True)

        self._price_segments: list[pg.PlotDataItem] = []
        self._avg_curve = self._price_plot.plot(
            pen=pg.mkPen(AVG_LINE_COLOR, width=INTRADAY_AVG_LINE_WIDTH),
        )
        self._last_dot = pg.ScatterPlotItem(
            size=INTRADAY_LAST_DOT_SIZE,
            pen=pg.mkPen(width=1.5),
            brush=pg.mkBrush(market_colors(theme_manager().tokens()).rise),
        )
        self._price_plot.addItem(self._last_dot)

        self._volume_bars = pg.BarGraphItem(x=[], height=[], width=VOLUME_BAR_WIDTH)
        self._volume_plot.addItem(self._volume_bars)

        self._prev_close_line = pg.InfiniteLine(
            angle=0,
            pen=pg.mkPen(PREV_CLOSE_COLOR, style=QtCore.Qt.PenStyle.DashLine, width=1),
        )
        self._price_plot.addItem(self._prev_close_line)

        self._proxy = pg.SignalProxy(
            self._gfx.scene().sigMouseMoved,
            rateLimit=30,
            slot=self._on_mouse_moved,
        )
        theme_manager().register_callback(self._on_theme_changed)

    def _on_theme_changed(self, tokens: ThemeTokens) -> None:
        self._palette = chart_palette(tokens)
        self._gfx.setBackground(self._palette.bg)
        style_intraday_price_plot(self._price_plot, self._palette)
        style_intraday_volume_plot(self._volume_plot, self._palette)
        cross_pen = pg.mkPen(self._palette.crosshair, width=1, style=QtCore.Qt.PenStyle.DashLine)
        self._vline.setPen(cross_pen)
        self._hline.setPen(cross_pen)
        self._vline_vol.setPen(cross_pen)
        if self._xs and self._prices:
            if self._prev_close > 0:
                self._update_price_layers(self._xs, self._prices, self._prev_close, tokens=tokens)
            self._update_last_dot(self._xs[-1], self._prices[-1], self._prev_close, tokens=tokens)
            self._update_volume_bars(self._xs, self._bars, tokens=tokens)
        if self._hover_index is not None:
            self._update_hover_summary(self._hover_index, tokens=tokens)
        else:
            self._update_idle_summary(tokens=tokens)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self._clear_hover()
        super().leaveEvent(event)

    def clear_all(self) -> None:
        self._bars = []
        self._xs = []
        self._prices = []
        self._avg_prices = []
        self._volumes = []
        self._prev_close = 0.0
        self._hover_index = None
        self._pct_axis.set_prev_close(0.0)
        self._info_bar.setText("—")
        self._avg_curve.setData([], [])
        self._last_dot.setData([], [])
        self._clear_price_segments()
        self._volume_bars.setOpts(x=[], height=[], width=VOLUME_BAR_WIDTH)
        self._prev_close_line.setPos(0)
        self._prev_close_line.hide()
        self._clear_hover()

    def _clear_hover(self) -> None:
        self._hover_index = None
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self._vline_vol.setVisible(False)
        self._update_idle_summary()

    def _clear_price_segments(self) -> None:
        for item in self._price_segments:
            self._price_plot.removeItem(item)
        self._price_segments.clear()

    def _update_price_layers(
        self,
        xs: list[float],
        prices: list[float],
        prev_close: float,
        *,
        tokens: ThemeTokens | None = None,
    ) -> None:
        """涨跌分段 2px 双色价格线。"""
        if tokens is None:
            tokens = theme_manager().tokens()
        colors = market_colors(tokens)
        self._clear_price_segments()
        if not xs or prev_close <= 0:
            return

        for seg_x, seg_y, rising in build_price_segments(xs, prices, prev_close):
            color = colors.rise if rising else colors.fall
            price_seg = pg.PlotDataItem(
                seg_x,
                seg_y,
                pen=pg.mkPen(color, width=INTRADAY_PRICE_LINE_WIDTH),
            )
            price_seg.setZValue(2)
            self._price_plot.addItem(price_seg)
            self._price_segments.append(price_seg)

        self._avg_curve.setZValue(1)
        self._last_dot.setZValue(3)

    def _update_last_dot(
        self,
        x: float,
        price: float,
        prev_close: float,
        *,
        tokens: ThemeTokens | None = None,
    ) -> None:
        color = change_color(price, prev_close, tokens=tokens)
        self._last_dot.setData([x], [price])
        self._last_dot.setPen(pg.mkPen(color, width=1.5))
        self._last_dot.setBrush(pg.mkBrush(color))

    def _update_volume_bars(
        self,
        xs: list[float],
        bars: list[BarData],
        *,
        tokens: ThemeTokens | None = None,
    ) -> None:
        volumes = [bar.volume for bar in bars]
        brushes = [pg.mkBrush(volume_bar_color(bar, tokens=tokens)) for bar in bars]
        self._volume_bars.setOpts(
            x=xs,
            height=volumes,
            width=VOLUME_BAR_WIDTH,
            brushes=brushes,
        )

    def _update_idle_summary(self, *, tokens: ThemeTokens | None = None) -> None:
        if not self._bars:
            self._info_bar.setText("—")
            return
        index = len(self._bars) - 1
        self._info_bar.setText(
            format_intraday_idle_summary(
                self._bars[index],
                avg_price=self._avg_prices[index],
                prev_close=self._prev_close,
                tokens=tokens,
            )
        )

    def _update_hover_summary(self, index: int, *, tokens: ThemeTokens | None = None) -> None:
        self._info_bar.setText(
            format_intraday_summary(
                self._bars[index],
                avg_price=self._avg_prices[index],
                prev_close=self._prev_close,
                tokens=tokens,
            )
        )

    def _show_hover(self, index: int) -> None:
        self._hover_index = index
        x = self._xs[index]
        price = self._prices[index]
        self._vline.setPos(x)
        self._hline.setPos(price)
        self._vline_vol.setPos(x)
        self._vline.setVisible(True)
        self._hline.setVisible(True)
        self._vline_vol.setVisible(True)
        self._update_hover_summary(index)

    def _mouse_over_chart(self, pos: QtCore.QPointF) -> bool:
        """判断鼠标是否在价格区或成交量区内（scene 坐标）。"""
        for plot in (self._price_plot, self._volume_plot):
            if plot.sceneBoundingRect().contains(pos):
                return True
        return False

    def _on_mouse_moved(self, event: object) -> None:
        if not self._xs:
            return
        pos = event[0]  # type: ignore[index]
        if not self._mouse_over_chart(pos):
            self._clear_hover()
            return
        mouse_point = self._price_plot.vb.mapSceneToView(pos)
        index = nearest_bar_index(self._xs, mouse_point.x())
        if index is None:
            self._clear_hover()
            return
        if index == self._hover_index:
            return
        self._show_hover(index)

    def update_bars(self, bars: list[BarData], *, prev_close: float = 0) -> None:
        if not bars:
            self.clear_all()
            return

        ordered = sorted(bars, key=lambda bar: bar.datetime)
        xs = session_x_values(ordered)
        prices = [bar.close_price for bar in ordered]
        avg_prices = calc_intraday_avg_prices(ordered)
        volumes = [bar.volume for bar in ordered]

        self._bars = ordered
        self._xs = xs
        self._prices = prices
        self._avg_prices = avg_prices
        self._volumes = volumes
        self._prev_close = prev_close
        self._pct_axis.set_prev_close(prev_close)

        self._avg_curve.setData(xs, avg_prices)
        self._update_volume_bars(xs, ordered)

        if prev_close > 0:
            self._prev_close_line.setPos(prev_close)
            self._prev_close_line.show()
            self._update_price_layers(xs, prices, prev_close)
        else:
            self._prev_close_line.hide()
            self._clear_price_segments()
            # 无昨收时仍绘制单色价格线
            fallback = pg.PlotDataItem(
                xs,
                prices,
                pen=pg.mkPen(market_colors(theme_manager().tokens()).flat, width=INTRADAY_PRICE_LINE_WIDTH),
            )
            fallback.setZValue(2)
            self._price_plot.addItem(fallback)
            self._price_segments.append(fallback)

        self._update_last_dot(xs[-1], prices[-1], prev_close)

        self._volume_plot.getAxis("bottom").setTicks([intraday_axis_ticks()])

        y_min, y_max = price_y_range(prices, prev_close=prev_close)
        vol_min, vol_max = volume_y_range(volumes)
        x_max = float(INTRADAY_SESSION_MINUTES)
        self._price_plot.setXRange(0, x_max, padding=0.01)
        self._price_plot.setYRange(y_min, y_max, padding=0)
        self._volume_plot.setXRange(0, x_max, padding=0.01)
        self._volume_plot.setYRange(vol_min, vol_max, padding=0)

        if self._hover_index is not None and 0 <= self._hover_index < len(self._bars):
            self._show_hover(self._hover_index)
        else:
            self._clear_hover()
