"""五档盘口面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import market_colors


class DepthPanel(QtWidgets.QFrame):
    """卖五 → 卖一 / 买一 → 买五。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DepthPanel")
        self.setMinimumWidth(148)
        self.setMaximumWidth(180)
        self._last_depth: DepthSnapshot | None = None

        title = QtWidgets.QLabel("五档盘口")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.table = QtWidgets.QTableWidget(10, 3)
        self.table.setObjectName("DepthTable")
        self.table.setHorizontalHeaderLabels(["", "价格", "量"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)

        self.hint_label = QtWidgets.QLabel("选中标的后显示")
        self.hint_label.setWordWrap(True)
        self.hint_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(title)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.hint_label)
        self.clear()

    def clear(self) -> None:
        self._last_depth = None
        self.table.setRowCount(10)
        for row in range(10):
            for col in range(3):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem("—"))
        self.hint_label.setText("选中标的后显示")

    def show_permission_denied(self, message: str) -> None:
        self._last_depth = None
        self.clear()
        self.hint_label.setText(message)

    def update_depth(self, depth: DepthSnapshot | None) -> None:
        if depth is None:
            self.clear()
            return

        self._last_depth = depth
        self.hint_label.setText("")
        asks = depth.ask_levels()
        bids = depth.bid_levels()

        for row in range(5):
            self._set_level_row(row, asks[row] if row < len(asks) else None, side="ask")
        for row in range(5):
            self._set_level_row(5 + row, bids[row] if row < len(bids) else None, side="bid")

    def refresh_colors(self) -> None:
        if self._last_depth is not None:
            self.update_depth(self._last_depth)

    def _set_level_row(
        self,
        row: int,
        level: tuple[int, float, int] | None,
        *,
        side: str,
    ) -> None:
        colors = market_colors(theme_manager().tokens())
        if level is None:
            values = ["—", "—", "—"]
            color = colors.flat
        else:
            label, price, volume = level
            prefix = "卖" if side == "ask" else "买"
            values = [f"{prefix}{label}", f"{price:.2f}", str(volume)]
            color = colors.fall if side == "ask" else colors.rise

        for col, text in enumerate(values):
            item = QtWidgets.QTableWidgetItem(text)
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if col > 0:
                item.setForeground(QtGui.QColor(color))
            self.table.setItem(row, col, item)
