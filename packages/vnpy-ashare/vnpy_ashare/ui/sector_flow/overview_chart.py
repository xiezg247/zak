"""板块资金概览：多折线 / 横向榜。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowOverviewSeries, SectorFlowOverviewSnapshot
from vnpy_ashare.services.sector_flow import format_sector_net_flow_yi
from vnpy_common.ui.theme.manager import theme_manager

_LINE_COLORS = (
    "#22c55e",
    "#3b82f6",
    "#a855f7",
    "#f97316",
    "#06b6d4",
    "#eab308",
    "#ec4899",
    "#84cc16",
    "#ef4444",
    "#6366f1",
    "#14b8a6",
    "#f43f5e",
    "#8b5cf6",
    "#10b981",
    "#0ea5e9",
    "#d946ef",
)


class SectorFlowOverviewChart(QtWidgets.QWidget):
    sector_activated = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowOverviewChart")
        self.setMinimumHeight(280)
        self._snapshot: SectorFlowOverviewSnapshot | None = None
        self._series: list[SectorFlowOverviewSeries] = []
        self._color_map: dict[str, str] = {}
        self._highlight_id: str = ""
        self._hover_bucket: str = ""
        self._hover_pos = QtCore.QPoint()
        self.setMouseTracking(True)
        theme_manager().register_callback(lambda _t: self.update())

    def render_snapshot(self, snapshot: SectorFlowOverviewSnapshot) -> None:
        self._snapshot = snapshot
        self._series = list(snapshot.inflow_series) + list(snapshot.outflow_series)
        self._color_map = {item.sector_id: _LINE_COLORS[index % len(_LINE_COLORS)] for index, item in enumerate(self._series)}
        self._highlight_id = ""
        self._hover_bucket = ""
        self.update()

    def set_highlight(self, sector_id: str) -> None:
        self._highlight_id = sector_id or ""
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        super().paintEvent(_event)
        snapshot = self._snapshot
        if snapshot is None or not self._series:
            return
        tokens = theme_manager().tokens()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        margin_left = 48
        margin_right = 12
        margin_top = 16
        margin_bottom = 28
        plot_left = margin_left
        plot_right = self.width() - margin_right
        plot_top = margin_top
        plot_bottom = self.height() - margin_bottom
        plot_w = max(plot_right - plot_left, 40)
        plot_h = max(plot_bottom - plot_top, 40)

        if snapshot.has_intraday_curve:
            self._paint_intraday_chart(
                painter,
                snapshot,
                plot_left,
                plot_top,
                plot_w,
                plot_h,
                tokens,
                margin_left=margin_left,
            )
        else:
            self._paint_bar_chart(painter, snapshot, plot_left, plot_top, plot_w, plot_h, tokens)
        painter.end()

    def _paint_intraday_chart(
        self,
        painter: QtGui.QPainter,
        snapshot: SectorFlowOverviewSnapshot,
        plot_left: float,
        plot_top: float,
        plot_w: float,
        plot_h: float,
        tokens,
        *,
        margin_left: float,
    ) -> None:
        axis = list(snapshot.time_axis)
        if not axis:
            return
        axis_index = {label: index for index, label in enumerate(axis)}
        values: list[float] = []
        for series in self._series:
            values.extend(point.net_flow_yi for point in series.points)
        max_abs = max((abs(value) for value in values), default=1.0)
        if max_abs <= 0:
            max_abs = 1.0
        max_abs *= 1.08

        def y_for(value: float) -> float:
            return plot_top + plot_h / 2 - (value / max_abs) * (plot_h / 2 - 4)

        zero_y = plot_top + plot_h / 2
        painter.setPen(QtGui.QPen(QtGui.QColor(tokens.panel_border), 1, QtCore.Qt.PenStyle.DashLine))
        painter.drawLine(int(plot_left), int(zero_y), int(plot_left + plot_w), int(zero_y))

        step = plot_w / max(len(axis) - 1, 1)

        def x_for_label(label: str) -> float:
            index = axis_index.get(label, 0)
            return plot_left + index * step

        painter.setPen(QtGui.QColor(tokens.text_secondary))
        for index, label in enumerate(axis):
            if index % 3 != 0 and index != len(axis) - 1:
                continue
            x = plot_left + index * step
            painter.drawText(QtCore.QRectF(x - 18, plot_top + plot_h + 4, 36, 16), int(QtCore.Qt.AlignmentFlag.AlignHCenter), label)

        painter.setPen(QtGui.QColor(tokens.text_secondary))
        for tick in (-max_abs, -max_abs / 2, 0, max_abs / 2, max_abs):
            y = y_for(tick)
            painter.drawText(QtCore.QRectF(4, y - 8, margin_left - 8, 16), int(QtCore.Qt.AlignmentFlag.AlignRight), f"{tick:+.0f}")

        for series in self._series:
            color = QtGui.QColor(self._color_map.get(series.sector_id, tokens.text_primary))
            alpha = 40 if self._highlight_id and self._highlight_id != series.sector_id else 255
            color.setAlpha(alpha)
            pen = QtGui.QPen(color, 2 if self._highlight_id == series.sector_id else 1.5)
            painter.setPen(pen)
            last_x = last_y = None
            for point in series.points:
                if point.bucket_time not in axis_index:
                    continue
                x = x_for_label(point.bucket_time)
                y = y_for(point.net_flow_yi)
                if last_x is not None and last_y is not None:
                    painter.drawLine(int(last_x), int(last_y), int(x), int(y))
                last_x, last_y = x, y

        if self._hover_bucket and self._hover_bucket in axis_index:
            x = x_for_label(self._hover_bucket)
            painter.setPen(QtGui.QPen(QtGui.QColor(tokens.text_secondary), 1, QtCore.Qt.PenStyle.DotLine))
            painter.drawLine(int(x), int(plot_top), int(x), int(plot_top + plot_h))
            self._paint_tooltip(painter, snapshot, self._hover_bucket, x_for_label=self._hover_bucket)

    def _paint_bar_chart(
        self,
        painter: QtGui.QPainter,
        snapshot: SectorFlowOverviewSnapshot,
        plot_left: float,
        plot_top: float,
        plot_w: float,
        plot_h: float,
        tokens,
    ) -> None:
        rows = list(snapshot.inflow_series) + list(snapshot.outflow_series)
        if not rows:
            return
        max_abs = max((abs(item.latest_yi) for item in rows), default=1.0)
        if max_abs <= 0:
            max_abs = 1.0
        bar_h = min(plot_h / max(len(rows), 1) - 4, 18)
        gap = 4
        y = plot_top
        for series in rows:
            ratio = abs(series.latest_yi) / max_abs
            width = max(ratio * (plot_w * 0.45), 2)
            color = QtGui.QColor(tokens.market_rise if series.latest_yi >= 0 else tokens.market_fall)
            if self._highlight_id and self._highlight_id != series.sector_id:
                color.setAlpha(80)
            painter.fillRect(QtCore.QRectF(plot_left, y, width, bar_h), color)
            painter.setPen(QtGui.QColor(tokens.text_primary))
            label = f"{series.name} {format_sector_net_flow_yi(series.latest_yi)}"
            painter.drawText(QtCore.QRectF(plot_left + width + 6, y, plot_w * 0.5, bar_h), int(QtCore.Qt.AlignmentFlag.AlignVCenter), label)
            y += bar_h + gap

    def _paint_tooltip(self, painter: QtGui.QPainter, snapshot: SectorFlowOverviewSnapshot, bucket: str, *, x_for_label: str) -> None:
        lines: list[str] = [bucket]
        for series in self._series:
            value = next((point.net_flow_yi for point in series.points if point.bucket_time == bucket), None)
            if value is None:
                continue
            lines.append(f"{series.name} {format_sector_net_flow_yi(value)}")
        if len(lines) <= 1:
            return
        text = "\n".join(lines[:9])
        font = painter.font()
        metrics = QtGui.QFontMetrics(font)
        width = min(max(metrics.horizontalAdvance(line) for line in lines[:9]) + 16, 220)
        height = metrics.lineSpacing() * min(len(lines), 9) + 10
        x = min(max(self._hover_pos.x() + 12, 8), self.width() - width - 8)
        y = min(max(self._hover_pos.y() - height - 8, 8), self.height() - height - 8)
        rect = QtCore.QRectF(x, y, width, height)
        painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
        painter.setBrush(QtGui.QColor(15, 23, 42, 230))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QtGui.QColor("#e2e8f0"))
        painter.drawText(rect.adjusted(8, 5, -8, -5), int(QtCore.Qt.TextFlag.TextWordWrap), text)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        snapshot = self._snapshot
        if snapshot is None or not snapshot.has_intraday_curve or not snapshot.time_axis:
            return
        margin_left = 48
        margin_right = 12
        plot_left = margin_left
        plot_w = max(self.width() - margin_left - margin_right, 40)
        axis = list(snapshot.time_axis)
        step = plot_w / max(len(axis) - 1, 1)
        rel_x = event.position().x() - plot_left
        index = int(round(rel_x / step)) if step > 0 else 0
        index = max(0, min(index, len(axis) - 1))
        bucket = axis[index]
        if bucket != self._hover_bucket:
            self._hover_bucket = bucket
            self._hover_pos = event.position().toPoint()
            self.update()

    def leaveEvent(self, _event: QtCore.QEvent) -> None:
        if self._hover_bucket:
            self._hover_bucket = ""
            self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        sector_id = self._sector_at(event.position().y())
        if sector_id:
            self.sector_activated.emit(sector_id)

    def _sector_at(self, y: float) -> str:
        snapshot = self._snapshot
        if snapshot is None or not self._series:
            return ""
        if snapshot.has_intraday_curve:
            return self._highlight_id
        rows = list(snapshot.inflow_series) + list(snapshot.outflow_series)
        margin_top = 16
        plot_h = max(self.height() - 44, 40)
        bar_h = min(plot_h / max(len(rows), 1) - 4, 18)
        gap = 4
        cursor = float(margin_top)
        for series in rows:
            if cursor <= y <= cursor + bar_h:
                return series.sector_id
            cursor += bar_h + gap
        return ""
