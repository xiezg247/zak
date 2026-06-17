"""雷达卡片单行标的组件。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.radar.radar_leader import leader_tier_label
from vnpy_ashare.quotes.radar.radar_loaders import RadarRow
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class RadarStockRowWidget(QtWidgets.QFrame):
    """结构化行：名称 / 指标 chip / 现价 / 涨幅 chip。"""

    clicked = QtCore.Signal(str)
    double_clicked = QtCore.Signal(str)
    add_watchlist_requested = QtCore.Signal(str)
    stock_analysis_requested = QtCore.Signal(str)

    def __init__(
        self,
        row: RadarRow,
        *,
        resonance: int = 0,
        show_add_watchlist_action: bool = True,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._row = row
        self._resonance = resonance
        self._show_add_watchlist_action = show_add_watchlist_action
        self._vt_symbol = row.vt_symbol
        self.setObjectName("RadarStockRow")
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

        self._resonance_badge = QtWidgets.QLabel("★" if resonance >= 2 else "")
        self._resonance_badge.setObjectName("RadarResonanceBadge")
        self._tier_badge = QtWidgets.QLabel("")
        self._tier_badge.setObjectName("RadarLeaderTierBadge")
        self._name_label = QtWidgets.QLabel(row.name)
        self._name_label.setObjectName("RadarRowName")
        self._symbol_label = QtWidgets.QLabel(row.symbol)
        self._symbol_label.setObjectName("RadarRowSymbol")

        name_col = QtWidgets.QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(0)
        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        title_row.addWidget(self._resonance_badge)
        title_row.addWidget(self._tier_badge)
        title_row.addWidget(self._name_label, stretch=1)
        name_col.addLayout(title_row)
        name_col.addWidget(self._symbol_label)

        self._metric_chip = QtWidgets.QLabel("")
        self._metric_chip.setObjectName("RadarMetricChip")
        self._sub_chip = QtWidgets.QLabel("")
        self._sub_chip.setObjectName("RadarSubChip")

        metric_col = QtWidgets.QVBoxLayout()
        metric_col.setContentsMargins(0, 0, 0, 0)
        metric_col.setSpacing(2)
        metric_col.addWidget(self._metric_chip)
        metric_col.addWidget(self._sub_chip)

        self._price_label = QtWidgets.QLabel("")
        self._price_label.setObjectName("RadarRowPrice")
        self._change_chip = QtWidgets.QLabel("")
        self._change_chip.setObjectName("RadarChangeChip")

        quote_col = QtWidgets.QVBoxLayout()
        quote_col.setContentsMargins(0, 0, 0, 0)
        quote_col.setSpacing(2)
        quote_col.addWidget(self._price_label, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        quote_col.addWidget(self._change_chip, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        layout.addLayout(name_col, stretch=3)
        layout.addLayout(metric_col, stretch=2)
        layout.addLayout(quote_col, stretch=2)

        self._apply_row()
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def vt_symbol(self) -> str:
        return self._vt_symbol

    def update_resonance(self, resonance: int) -> None:
        self._resonance = resonance
        self._resonance_badge.setText("★" if resonance >= 2 else "")
        font = self._name_label.font()
        font.setBold(resonance >= 2)
        self._name_label.setFont(font)

    def update_quotes(self, price: float | None, change_pct: float | None) -> None:
        """增量刷新现价与涨幅，保留指标 chip。"""
        if price == self._row.price and change_pct == self._row.change_pct:
            return

        self._row = self._row.model_copy(update={"price": price, "change_pct": change_pct})
        self._apply_row()

    def refresh_theme(self) -> None:
        self._apply_row()

    def _apply_row(self) -> None:
        row = self._row
        tier_label = leader_tier_label(row.leader_tier)
        if tier_label:
            self._tier_badge.setText(tier_label)
            self._tier_badge.show()
            tokens = theme_manager().tokens()
            tier_color = tokens.text_secondary
            if row.leader_tier == "dragon_1":
                tier_color = pct_change_color(1.0, tokens)
            elif row.leader_tier == "dragon_2":
                tier_color = tokens.accent
            self._tier_badge.setStyleSheet(
                f"color: {tier_color}; background-color: {tokens.panel_bg}; "
                f"border: 1px solid {tokens.panel_border}; "
                f"border-radius: 3px; padding: 0 4px; font-size: 11px; font-weight: 600;"
            )
        else:
            self._tier_badge.hide()
        if row.metric_label and row.metric_value:
            self._metric_chip.setText(f"{row.metric_label} {row.metric_value}")
            self._metric_chip.show()
        else:
            self._metric_chip.hide()
        if row.sub_label and row.sub_value:
            self._sub_chip.setText(f"{row.sub_label} {row.sub_value}")
            self._sub_chip.show()
        else:
            self._sub_chip.hide()
        price = f"{row.price:.2f}" if row.price is not None else "—"
        self._price_label.setText(price)
        change = f"{row.change_pct:+.2f}%" if row.change_pct is not None else "—"
        self._change_chip.setText(change)
        tokens = theme_manager().tokens()
        change_color = pct_change_color(row.change_pct, tokens)
        self._change_chip.setStyleSheet(
            f"color: {change_color}; background-color: {tokens.panel_bg}; "
            f"border: 1px solid {tokens.panel_border}; "
            f"border-radius: 4px; padding: 2px 6px; font-weight: 600;"
        )
        font = self._name_label.font()
        font.setBold(self._resonance >= 2)
        self._name_label.setFont(font)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self._vt_symbol)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._vt_symbol)
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        analysis_action = menu.addAction("个股分析")
        add_action = None
        if self._show_add_watchlist_action:
            add_action = menu.addAction("加入自选")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is analysis_action:
            self.stock_analysis_requested.emit(self._vt_symbol)
        elif add_action is not None and chosen is add_action:
            self.add_watchlist_requested.emit(self._vt_symbol)
