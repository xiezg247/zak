"""板块近 N 日主力净流入迷你柱。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint
from vnpy_common.ui.theme.manager import theme_manager


def _format_trade_date_short(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[4:6]}-{cleaned[6:8]}"
    if len(cleaned) >= 5 and "-" in cleaned:
        return cleaned[-5:]
    return cleaned


class SectorFlowMiniBar(QtWidgets.QWidget):
    """侧栏紧凑主力净流入柱（默认近 5 日）。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, max_points: int = 5) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowMiniBar")
        self._max_points = max(1, max_points)
        self.setMinimumHeight(64)
        self._points: list[SectorFlowHistoryPoint] = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        theme_manager().register_callback(lambda _t: self.update())

    def render_points(self, points: list[SectorFlowHistoryPoint]) -> None:
        trimmed = list(points)[-self._max_points :]
        self._points = trimmed
        self.update()

    def clear(self) -> None:
        self._points = []
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        super().paintEvent(_event)
        if not self._points:
            return
        tokens = theme_manager().tokens()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        top = 6
        bottom = self.height() - 16
        chart_height = max(bottom - top, 12)
        left = 8
        right = self.width() - 8
        width = max(right - left, 40)
        count = len(self._points)
        gap = 6
        bar_width = max((width - gap * (count - 1)) / count, 8)
        values = [point.net_flow_yi for point in self._points]
        max_abs = max((abs(value) for value in values), default=1.0)
        if max_abs <= 0:
            max_abs = 1.0
        zero_y = top + chart_height / 2

        painter.setPen(QtGui.QPen(QtGui.QColor(tokens.panel_border), 1))
        painter.drawLine(int(left), int(zero_y), int(right), int(zero_y))

        for index, point in enumerate(self._points):
            x = left + index * (bar_width + gap)
            value = point.net_flow_yi
            bar_h = abs(value) / max_abs * (chart_height / 2 - 2)
            if value >= 0:
                color = QtGui.QColor(tokens.market_rise)
                y = zero_y - bar_h
            else:
                color = QtGui.QColor(tokens.market_fall)
                y = zero_y
            painter.fillRect(QtCore.QRectF(x, y, bar_width, max(bar_h, 2)), color)
            painter.setPen(QtGui.QColor(tokens.text_secondary))
            label = _format_trade_date_short(point.trade_date)
            painter.drawText(
                QtCore.QRectF(x - 2, bottom, bar_width + 4, 14),
                int(QtCore.Qt.AlignmentFlag.AlignHCenter),
                label,
            )
        painter.end()
