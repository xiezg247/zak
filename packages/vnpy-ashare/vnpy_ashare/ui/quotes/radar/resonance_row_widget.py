"""雷达共振列表单行组件。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.radar.radar_models import RadarResonanceEntry
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class RadarResonanceRowWidget(QtWidgets.QFrame):
    """结构化共振行：名称 / 卡数·加权 / 现价 / 涨幅 / 来源卡。"""

    clicked = QtCore.Signal()
    double_clicked = QtCore.Signal()

    MIN_ROW_HEIGHT = 64

    def __init__(self, entry: RadarResonanceEntry, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._selected = False
        self.setObjectName("RadarResonanceRow")
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

        self._badge = QtWidgets.QLabel("★")
        self._badge.setObjectName("RadarResonanceBadge")

        self._name_label = QtWidgets.QLabel(entry.name)
        self._name_label.setObjectName("RadarResonanceRowName")

        self._count_chip = QtWidgets.QLabel("")
        self._count_chip.setObjectName("RadarResonanceCountChip")

        self._price_label = QtWidgets.QLabel("")
        self._price_label.setObjectName("RadarResonanceRowPrice")
        self._change_chip = QtWidgets.QLabel("")
        self._change_chip.setObjectName("RadarResonanceChangeChip")

        self._symbol_label = QtWidgets.QLabel(entry.symbol)
        self._symbol_label.setObjectName("RadarResonanceRowSymbol")

        self._cards_label = QtWidgets.QLabel("")
        self._cards_label.setObjectName("RadarResonanceRowCards")
        self._cards_label.setWordWrap(True)

        name_row = QtWidgets.QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(4)
        name_row.addWidget(self._badge)
        name_row.addWidget(self._name_label)
        name_row.addWidget(self._count_chip)
        name_row.addStretch()

        quote_row = QtWidgets.QHBoxLayout()
        quote_row.setContentsMargins(0, 0, 0, 0)
        quote_row.setSpacing(6)
        quote_row.addWidget(self._price_label)
        quote_row.addWidget(self._change_chip)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addLayout(name_row, stretch=1)
        top_row.addLayout(quote_row)

        symbol_row = QtWidgets.QHBoxLayout()
        symbol_row.setContentsMargins(0, 0, 0, 0)
        symbol_row.setSpacing(0)
        symbol_row.addSpacing(16)
        symbol_row.addWidget(self._symbol_label, stretch=1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)
        layout.addLayout(top_row)
        layout.addLayout(symbol_row)
        layout.addWidget(self._cards_label)

        self._apply_entry()
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

    def vt_symbol(self) -> str:
        return self._entry.vt_symbol

    def refresh_theme(self) -> None:
        self._apply_entry()
        self._apply_selected_style()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_selected_style()

    def _apply_selected_style(self) -> None:
        self.setProperty("selected", self._selected)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def sizeHint(self) -> QtCore.QSize:
        cards_h = self._cards_label.sizeHint().height()
        base = max(self.MIN_ROW_HEIGHT, 52 + cards_h)
        return QtCore.QSize(0, base)

    def minimumSizeHint(self) -> QtCore.QSize:
        return self.sizeHint()

    def _apply_entry(self) -> None:
        entry = self._entry
        count_text = f"{entry.card_count} 卡"
        if entry.resonance_score > 0:
            count_text = f"{count_text} · {entry.resonance_score:.1f}"
        if entry.leader_tier == "dragon_1":
            count_text = f"龙一 · {count_text}"
        elif entry.leader_tier == "dragon_2":
            count_text = f"龙二 · {count_text}"
        if entry.limit_times is not None and entry.limit_times >= 1:
            count_text = f"{count_text} · {int(entry.limit_times)}板"
        self._count_chip.setText(count_text)
        self._cards_label.setText(" · ".join(entry.card_titles))

        price = f"{entry.price:.2f}" if entry.price is not None else "—"
        self._price_label.setText(price)
        change = f"{entry.change_pct:+.2f}%" if entry.change_pct is not None else "—"
        self._change_chip.setText(change)

        tokens = theme_manager().tokens()
        change_color = pct_change_color(entry.change_pct, tokens)
        self._change_chip.setStyleSheet(
            f"color: {change_color}; background-color: {tokens.panel_bg}; "
            f"border: 1px solid {tokens.panel_border}; "
            f"border-radius: 4px; padding: 2px 6px; font-weight: 600; font-size: 11px;"
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)
