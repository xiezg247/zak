"""行业榜卡片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.market_overview_loaders import SectorRankItem
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


class SectorCardWidget(QtWidgets.QFrame):
    """单张行业榜卡片（双击选中行业）。"""

    activated = QtCore.Signal(str)

    def __init__(
        self,
        item: SectorRankItem,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._selected = False
        self.setObjectName("SectorCard")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{item.industry}：{item.count} 只，平均涨幅 {item.avg_change_pct:+.2f}%（双击筛选）")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._name_label = QtWidgets.QLabel(item.industry)
        self._name_label.setObjectName("SectorCardName")
        layout.addWidget(self._name_label)

        self._pct_label = QtWidgets.QLabel(f"{item.avg_change_pct:+.2f}%")
        self._pct_label.setObjectName("SectorCardPct")
        layout.addWidget(self._pct_label)

        self._count_label = QtWidgets.QLabel(f"{item.count} 只")
        self._count_label.setObjectName("SectorCardCount")
        layout.addWidget(self._count_label)

        self._apply_colors()
        self._apply_frame_style()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.activated.emit(self._item.industry)
        super().mouseDoubleClickEvent(event)

    def _apply_colors(self) -> None:
        tokens = theme_manager().tokens()
        color = pct_change_color(self._item.avg_change_pct, tokens)
        self._pct_label.setStyleSheet(f"color: {color};")

    def update_item(self, item: SectorRankItem) -> None:
        self._item = item
        self._name_label.setText(item.industry)
        self._pct_label.setText(f"{item.avg_change_pct:+.2f}%")
        self._count_label.setText(f"{item.count} 只")
        self.setToolTip(f"{item.industry}：{item.count} 只，平均涨幅 {item.avg_change_pct:+.2f}%（双击筛选）")
        self._apply_colors()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_frame_style()

    def _apply_frame_style(self) -> None:
        tokens = theme_manager().tokens()
        border = tokens.accent if self._selected else tokens.panel_border
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"QFrame#SectorCard {{ background-color: {tokens.panel_bg}; border: {width}px solid {border}; border-radius: 6px; min-width: 96px; }}"
        )
