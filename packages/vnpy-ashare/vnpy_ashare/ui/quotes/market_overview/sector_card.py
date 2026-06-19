"""行业榜卡片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.integrations.tushare.sw_industry import format_industry_filter_label
from vnpy_ashare.quotes.market.market_overview_loaders import SectorRankItem
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


def _sector_card_tooltip(item: SectorRankItem) -> str:
    title = format_industry_filter_label(item.industry, item.industry_l1)
    return f"{title}：{item.count} 只，平均涨幅 {item.avg_change_pct:+.2f}%（双击按 L2 筛选）"


class SectorCardWidget(QtWidgets.QFrame):
    """单张行业榜卡片（双击选中申万 L2 行业）。"""

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
        self.setToolTip(_sector_card_tooltip(item))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._l1_label = QtWidgets.QLabel(item.industry_l1 or "")
        self._l1_label.setObjectName("SectorCardL1")
        layout.addWidget(self._l1_label)
        self._sync_l1_visibility()

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

    def _sync_l1_visibility(self) -> None:
        visible = bool(str(self._item.industry_l1 or "").strip())
        self._l1_label.setVisible(visible)
        if visible:
            self._l1_label.setText(str(self._item.industry_l1))

    def _apply_colors(self) -> None:
        tokens = theme_manager().tokens()
        color = pct_change_color(self._item.avg_change_pct, tokens)
        self._pct_label.setStyleSheet(f"color: {color};")

    def update_item(self, item: SectorRankItem) -> None:
        self._item = item
        self._name_label.setText(item.industry)
        self._pct_label.setText(f"{item.avg_change_pct:+.2f}%")
        self._count_label.setText(f"{item.count} 只")
        self._sync_l1_visibility()
        self.setToolTip(_sector_card_tooltip(item))
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
