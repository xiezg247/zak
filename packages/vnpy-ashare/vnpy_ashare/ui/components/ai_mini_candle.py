"""AI 聊天内嵌迷你 K 线图。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ai.protocol import AiChartBar, AiChartSpec
from vnpy_common.ui.theme.manager import theme_manager

_CANDLE_FLAT_EPS = 1e-4
_PRICE_TOP = 8
_VOLUME_LABEL_HEIGHT = 14
_MA_COLORS = {
    5: "#ffb020",
    10: "#c9a227",
    20: "#5b9cf5",
    60: "#a78bfa",
}


def _is_up_bar(bar: AiChartBar) -> bool:
    flat = abs(bar.close - bar.open) < _CANDLE_FLAT_EPS
    return flat or bar.close >= bar.open


def _compute_ma(closes: list[float], period: int) -> list[float | None]:
    values: list[float | None] = []
    for index in range(len(closes)):
        if index + 1 < period:
            values.append(None)
            continue
        window = closes[index + 1 - period : index + 1]
        values.append(sum(window) / period)
    return values


def _overlay_periods(overlays: list[dict[str, object]]) -> list[int]:
    periods: list[int] = []
    for item in overlays:
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") != "ma":
            continue
        try:
            period = int(item.get("period") or 0)
        except (TypeError, ValueError):
            continue
        if period > 1 and period not in periods:
            periods.append(period)
    return sorted(periods)


class AiMiniCandleChart(QtWidgets.QWidget):
    """紧凑 K 线 + 成交量副图 + MA 叠加。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiMiniCandleChart")
        self._bars: list[AiChartBar] = []
        self._overlays: list[dict[str, object]] = []
        self.setMinimumHeight(168)
        self.setMaximumHeight(168)
        theme_manager().register_callback(lambda _tokens: self.update())

    def render_spec(self, spec: AiChartSpec) -> None:
        self._bars = list(spec.series)
        self._overlays = list(spec.overlays)
        self.update()

    def clear(self) -> None:
        self._bars = []
        self._overlays = []
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        super().paintEvent(_event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        tokens = theme_manager().tokens()
        painter.fillRect(self.rect(), QtGui.QColor(tokens.depth_bg))

        if not self._bars:
            painter.setPen(QtGui.QColor(tokens.text_muted))
            painter.drawText(self.rect(), int(QtCore.Qt.AlignmentFlag.AlignCenter), "暂无 K 线数据")
            painter.end()
            return

        left = 8
        right = max(self.width() - 8, left + 40)
        width = right - left
        volume_top = self.height() - _VOLUME_LABEL_HEIGHT - 36
        price_bottom = volume_top - 6
        price_top = _PRICE_TOP
        price_height = max(price_bottom - price_top, 20)
        volume_height = 30

        lows = [bar.low for bar in self._bars]
        highs = [bar.high for bar in self._bars]
        closes = [bar.close for bar in self._bars]
        price_min = min(lows)
        price_max = max(highs)

        overlay_periods = _overlay_periods(self._overlays)
        ma_lines: dict[int, list[float | None]] = {period: _compute_ma(closes, period) for period in overlay_periods}
        for values in ma_lines.values():
            for value in values:
                if value is not None:
                    price_min = min(price_min, value)
                    price_max = max(price_max, value)

        if price_max <= price_min:
            price_max = price_min + 1.0
        price_pad = (price_max - price_min) * 0.06
        price_min -= price_pad
        price_max += price_pad

        volumes = [float(bar.volume) for bar in self._bars]
        max_volume = max(volumes) if volumes else 1.0
        if max_volume <= 0:
            max_volume = 1.0

        count = len(self._bars)
        gap = 2
        body_width = max((width - gap * (count - 1)) / count, 2.0)
        rise = QtGui.QColor(tokens.market_rise)
        fall = QtGui.QColor(tokens.market_fall)

        def price_y(value: float) -> float:
            ratio = (value - price_min) / (price_max - price_min)
            return price_bottom - ratio * price_height

        def center_x(index: int) -> float:
            return left + index * (body_width + gap) + body_width / 2

        painter.setPen(QtGui.QPen(QtGui.QColor(tokens.panel_border), 1))
        painter.drawLine(int(left), int(price_bottom), int(right), int(price_bottom))
        volume_base = volume_top + volume_height

        for index, bar in enumerate(self._bars):
            x = center_x(index)
            up = _is_up_bar(bar)
            color = rise if up else fall
            painter.setPen(QtGui.QPen(color, 1))
            painter.setBrush(QtGui.QBrush(color if not up else rise))

            high_y = price_y(bar.high)
            low_y = price_y(bar.low)
            open_y = price_y(bar.open)
            close_y = price_y(bar.close)
            painter.drawLine(QtCore.QPointF(x, high_y), QtCore.QPointF(x, low_y))

            flat = abs(bar.close - bar.open) < _CANDLE_FLAT_EPS
            if flat:
                mid_y = (open_y + close_y) / 2
                painter.drawLine(
                    QtCore.QPointF(x - body_width / 2, mid_y),
                    QtCore.QPointF(x + body_width / 2, mid_y),
                )
            else:
                top_y = min(open_y, close_y)
                bottom_y = max(open_y, close_y)
                rect_height = max(bottom_y - top_y, 1.0)
                painter.drawRect(
                    QtCore.QRectF(x - body_width / 2, top_y, body_width, rect_height),
                )

            if bar.volume > 0:
                vol_h = bar.volume / max_volume * volume_height
                vol_top = volume_base - vol_h
                painter.fillRect(
                    QtCore.QRectF(x - body_width / 2, vol_top, body_width, max(vol_h, 1.0)),
                    color,
                )

        for period, values in ma_lines.items():
            color = _MA_COLORS.get(period, tokens.text_secondary)
            pen = QtGui.QPen(QtGui.QColor(color), 1.0)
            painter.setPen(pen)
            path = QtGui.QPainterPath()
            started = False
            for index, value in enumerate(values):
                if value is None:
                    started = False
                    continue
                x = center_x(index)
                y = price_y(value)
                if not started:
                    path.moveTo(x, y)
                    started = True
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

        painter.setPen(QtGui.QColor(tokens.text_muted))
        first_date = self._bars[0].date
        last_date = self._bars[-1].date
        painter.drawText(
            QtCore.QRectF(left, volume_base + 2, width / 2, _VOLUME_LABEL_HEIGHT),
            int(QtCore.Qt.AlignmentFlag.AlignLeft),
            first_date[-5:] if len(first_date) >= 5 else first_date,
        )
        painter.drawText(
            QtCore.QRectF(left + width / 2, volume_base + 2, width / 2, _VOLUME_LABEL_HEIGHT),
            int(QtCore.Qt.AlignmentFlag.AlignRight),
            last_date[-5:] if len(last_date) >= 5 else last_date,
        )
        painter.end()
