"""自选多维看盘单票卡片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.format import format_pct
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiRow
from vnpy_ashare.ui.quotes.watchlist_multiview.sparkline import DailySparkline
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_ANOMALY_BADGE_THRESHOLD = 12.0


class WatchlistMultiCard(QtWidgets.QFrame):
    """单票多维卡片：迷你日K + 价量 + 指标 chip。"""

    clicked = QtCore.Signal(str)
    double_clicked = QtCore.Signal(str)
    context_menu_requested = QtCore.Signal(str, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WatchlistMultiCard")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setMinimumHeight(132)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._vt_symbol = ""
        self._change_pct: float | None = None
        self._selected = False

        self._anomaly_badge = QtWidgets.QLabel("")
        self._anomaly_badge.setObjectName("WatchlistMultiAnomalyBadge")
        self._name_label = QtWidgets.QLabel("—")
        self._name_label.setObjectName("WatchlistMultiName")
        self._symbol_label = QtWidgets.QLabel("")
        self._symbol_label.setObjectName("WatchlistMultiSymbol")

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        title_row.addWidget(self._anomaly_badge)
        title_row.addWidget(self._name_label, stretch=1)

        name_col = QtWidgets.QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(0)
        name_col.addLayout(title_row)
        name_col.addWidget(self._symbol_label)

        self._price_label = QtWidgets.QLabel("—")
        self._price_label.setObjectName("WatchlistMultiPrice")
        self._change_chip = QtWidgets.QLabel("")
        self._change_chip.setObjectName("WatchlistMultiChangeChip")

        quote_col = QtWidgets.QVBoxLayout()
        quote_col.setContentsMargins(0, 0, 0, 0)
        quote_col.setSpacing(2)
        quote_col.addWidget(self._price_label, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        quote_col.addWidget(self._change_chip, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addLayout(name_col, stretch=3)
        header.addLayout(quote_col, stretch=2)

        self._sparkline = DailySparkline()
        self._sparkline_kind_label = QtWidgets.QLabel("")
        self._sparkline_kind_label.setObjectName("WatchlistMultiSparklineKind")

        sparkline_row = QtWidgets.QHBoxLayout()
        sparkline_row.setContentsMargins(0, 0, 0, 0)
        sparkline_row.addWidget(self._sparkline, stretch=1)
        sparkline_row.addWidget(self._sparkline_kind_label, alignment=QtCore.Qt.AlignmentFlag.AlignTop)

        self._signal_badge = QtWidgets.QLabel("")
        self._signal_badge.setObjectName("WatchlistMultiSignalBadge")
        self._position_badge = QtWidgets.QLabel("")
        self._position_badge.setObjectName("WatchlistMultiPositionBadge")
        self._sector_badge = QtWidgets.QLabel("")
        self._sector_badge.setObjectName("WatchlistMultiSectorBadge")

        badges = QtWidgets.QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(6)
        badges.addWidget(self._signal_badge)
        badges.addWidget(self._position_badge)
        badges.addWidget(self._sector_badge)
        badges.addStretch(1)

        self._metric_chip = QtWidgets.QLabel("")
        self._metric_chip.setObjectName("WatchlistMultiMetricChip")
        self._sub_chip = QtWidgets.QLabel("")
        self._sub_chip.setObjectName("WatchlistMultiSubChip")

        chips = QtWidgets.QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        chips.addWidget(self._metric_chip)
        chips.addWidget(self._sub_chip)
        chips.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addLayout(sparkline_row, stretch=1)
        layout.addLayout(badges)
        layout.addLayout(chips)

        theme_manager().register_callback(lambda _tokens: self._refresh_colors())

    def apply_row(self, row: WatchlistMultiRow, *, selected: bool = False) -> None:
        self._vt_symbol = row.vt_symbol
        self._change_pct = row.change_pct
        self._selected = selected
        self._name_label.setText(row.name)
        self._symbol_label.setText(row.symbol)
        self._price_label.setText(f"{row.last_price:.2f}" if row.last_price is not None else "—")
        change_text = format_pct(row.change_pct) if row.change_pct is not None else "—"
        self._change_chip.setText(change_text)
        self._metric_chip.setText(f"{row.metric_label} {row.metric_value}")
        self._sub_chip.setText(f"{row.sub_label} {row.sub_value}")
        self._anomaly_badge.setText("●" if row.anomaly_score >= _ANOMALY_BADGE_THRESHOLD else "")
        self._anomaly_badge.setToolTip(f"异动分 {row.anomaly_score:.1f}" if row.anomaly_score >= _ANOMALY_BADGE_THRESHOLD else "")
        self._apply_badge(self._signal_badge, f"信号 {row.signal_label}" if row.signal_label else "")
        if row.has_position and row.position_pnl_pct is not None:
            self._apply_badge(self._position_badge, f"持仓 {row.position_pnl_pct:+.2f}%")
        elif row.has_position:
            self._apply_badge(self._position_badge, "持仓")
        else:
            self._apply_badge(self._position_badge, "")
        if row.industry and row.sector_rank is not None:
            sector_text = f"{row.industry} #{row.sector_rank}"
            if row.sector_avg_change is not None:
                sector_text += f" {row.sector_avg_change:+.2f}%"
            self._apply_badge(self._sector_badge, sector_text)
        elif row.industry:
            self._apply_badge(self._sector_badge, row.industry)
        else:
            self._apply_badge(self._sector_badge, "")
        if row.sparkline_points:
            self._sparkline.render_points(row.sparkline_points)
            kind_text = {"intraday": "分时", "daily": "日K", "minute": "分K"}.get(row.sparkline_kind, "")
            self._sparkline_kind_label.setText(kind_text)
            self._sparkline_kind_label.setVisible(bool(kind_text))
        else:
            self._sparkline.clear()
            self._sparkline_kind_label.hide()
        self._refresh_colors()
        self._apply_selected_style()

    def vt_symbol(self) -> str:
        return self._vt_symbol

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_selected_style()

    def _apply_badge(self, label: QtWidgets.QLabel, text: str) -> None:
        cleaned = (text or "").strip()
        label.setText(cleaned)
        label.setVisible(bool(cleaned))

    def _apply_selected_style(self) -> None:
        self.setProperty("selected", self._selected)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def _refresh_colors(self) -> None:
        tokens = theme_manager().tokens()
        color = pct_change_color(self._change_pct, tokens)
        self._change_chip.setStyleSheet(f"color: {color};")

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._vt_symbol:
            self.clicked.emit(self._vt_symbol)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._vt_symbol:
            self.double_clicked.emit(self._vt_symbol)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        if self._vt_symbol:
            self.context_menu_requested.emit(self._vt_symbol, event.globalPos())
        super().contextMenuEvent(event)
