"""Playbook 紧凑规则表。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.home.playbook_markdown_tables import PlaybookTableBlock


class PlaybookRuleTable(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybookRuleTable")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        self._title = QtWidgets.QLabel("")
        self._title.setObjectName("PlaybookRuleTableTitle")

        self._table = QtWidgets.QTableWidget(0, 0)
        self._table.setObjectName("PlaybookRuleTableView")
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)

        root.addWidget(self._title)
        root.addWidget(self._table, stretch=1)

    def apply_block(self, block: PlaybookTableBlock) -> None:
        self._title.setText(block.title)
        self._table.clear()
        self._table.setColumnCount(len(block.headers))
        self._table.setHorizontalHeaderLabels(list(block.headers))
        self._table.setRowCount(len(block.rows))
        for row_index, row in enumerate(block.rows):
            for col_index, value in enumerate(row):
                if col_index >= len(block.headers):
                    break
                item = QtWidgets.QTableWidgetItem(value)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(row_index, col_index, item)
        self._table.resizeRowsToContents()
        self.show()

    def clear_block(self) -> None:
        self._title.clear()
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self.hide()
