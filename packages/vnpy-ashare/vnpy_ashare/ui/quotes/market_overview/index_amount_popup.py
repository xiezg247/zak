"""指数历史成交额弹窗。"""

from __future__ import annotations

import pyqtgraph as pg
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.index_amount import IndexAmountSeries
from vnpy_ashare.ui.components.chart_style import apply_sparkline_plot_theme
from vnpy_common.ui.theme import theme_manager


class IndexAmountPopup(QtWidgets.QFrame):
    """单指数近 N 日成交额折线弹窗。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setObjectName("IndexAmountPopup")
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)

        self._title = QtWidgets.QLabel("")
        self._title.setObjectName("IndexAmountPopupTitle")
        self._summary = QtWidgets.QLabel("加载中…")
        self._summary.setObjectName("IndexAmountPopupSummary")
        self._summary.setWordWrap(True)

        self._plot = pg.PlotWidget()
        self._plot.setObjectName("IndexAmountPopupPlot")
        self._plot.setMinimumHeight(140)
        self._plot.setMaximumHeight(160)
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        self._plot.setLabel("left", "成交额", units="亿")
        apply_sparkline_plot_theme(self._plot)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self._title)
        layout.addWidget(self._summary)
        layout.addWidget(self._plot)

        theme_manager().register_callback(lambda _t: self._apply_theme())

    def show_loading(self, *, label: str, trading_days: int) -> None:
        self._title.setText(f"{label} · 近{trading_days}日成交额")
        self._summary.setText("加载中…")
        self._plot.clear()

    def show_error(self, *, label: str, trading_days: int, message: str) -> None:
        self._title.setText(f"{label} · 近{trading_days}日成交额")
        self._summary.setText(message)
        self._plot.clear()

    def render(self, series: IndexAmountSeries, *, trading_days: int) -> None:
        self._title.setText(f"{series.label} · 近{trading_days}日成交额")
        self._plot.clear()
        if series.error:
            self.show_error(label=series.label, trading_days=trading_days, message=series.error)
            return
        if not series.points:
            self.show_error(
                label=series.label,
                trading_days=trading_days,
                message="暂无历史成交额数据",
            )
            return

        values = [point.amount_yi for point in series.points]
        xs = list(range(len(values)))
        tokens = theme_manager().tokens()
        self._plot.plot(xs, values, pen=pg.mkPen(color=tokens.accent, width=1.8), clear=False)

        avg = series.avg_yi
        if avg > 0:
            self._plot.addLine(y=avg, pen=pg.mkPen(color=tokens.text_muted, width=1, style=QtCore.Qt.PenStyle.DashLine))

        ratio = series.ratio_to_avg
        ratio_text = f"{ratio:.2f}" if ratio is not None else "—"
        self._summary.setText(f"今日 {series.latest_yi:.2f} 亿 · 均值 {avg:.2f} 亿 · 比值 {ratio_text}")

        axis = self._plot.getPlotItem().getAxis("bottom")
        if axis is not None:
            ticks = []
            if len(series.points) >= 2:
                for index in (0, len(series.points) - 1):
                    date_text = series.points[index].trade_date
                    if len(date_text) == 8:
                        date_text = f"{date_text[4:6]}-{date_text[6:8]}"
                    ticks.append((index, date_text))
            axis.setTicks([ticks])

    def show_near(self, anchor: QtWidgets.QWidget) -> None:
        global_pos = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height() + 4))
        screen = anchor.screen() or QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            size_hint = self.sizeHint()
            width = max(self.minimumWidth(), min(size_hint.width(), self.maximumWidth()))
            height = max(size_hint.height(), self.minimumHeight())
            x = min(global_pos.x(), available.right() - width)
            y = min(global_pos.y(), available.bottom() - height)
            x = max(available.left(), x)
            y = max(available.y(), y)
            self.setFixedWidth(width)
            self.move(x, y)
        else:
            self.move(global_pos)
        self.show()
        self.raise_()

    def _apply_theme(self) -> None:
        apply_sparkline_plot_theme(self._plot)
        self.setStyleSheet(
            f"""
            QFrame#IndexAmountPopup {{
                background-color: {theme_manager().tokens().panel_bg};
                border: 1px solid {theme_manager().tokens().panel_border};
                border-radius: 8px;
            }}
            QLabel#IndexAmountPopupTitle {{
                color: {theme_manager().tokens().text_primary};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#IndexAmountPopupSummary {{
                color: {theme_manager().tokens().text_secondary};
                font-size: 11px;
            }}
            """
        )
