"""选股批量回测结果对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.screener.batch_actions import BatchBacktestRow
from vnpy_ashare.screener.export import export_rows_to_csv
from vnpy_common.ui.theme import theme_manager


class ScreenerBatchBacktestDialog(QtWidgets.QDialog):
    def __init__(
        self,
        rows: list[BatchBacktestRow],
        *,
        class_name: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows = rows
        self.setWindowTitle("批量回测结果")
        self.setMinimumSize(720, 420)
        theme_manager().bind_stylesheet(self)
        self._build_ui(class_name)

    def _build_ui(self, class_name: str) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        summary = QtWidgets.QLabel(f"策略：{class_name} · 共 {len(self._rows)} 只")
        layout.addWidget(summary)

        headers = ["代码", "名称", "总收益", "最大回撤", "夏普", "交易次数", "备注"]
        table = QtWidgets.QTableWidget(len(self._rows), len(headers))
        table.setObjectName("MarketTable")
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        if hasattr(header, "setStretchHighlightSections"):
            header.setStretchHighlightSections(False)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)

        for row_index, row in enumerate(self._rows):
            values = [
                row.vt_symbol,
                row.name,
                self._fmt(row.total_return),
                self._fmt(row.max_drawdown),
                self._fmt(row.sharpe_ratio),
                str(row.total_trade_count if row.total_trade_count is not None else "—"),
                row.error or "—",
            ]
            for col_index, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, col_index, item)
        layout.addWidget(table, stretch=1)

        footer = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QPushButton("导出 CSV")
        export_btn.clicked.connect(self._export_csv)
        footer.addWidget(export_btn)
        footer.addStretch()
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    @staticmethod
    def _fmt(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:.2f}"

    def _export_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出批量回测",
            "screener_batch_backtest.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        export_rows_to_csv([row.to_dict() for row in self._rows], path)
        QtWidgets.QMessageBox.information(self, "提示", f"已导出：{path}")


class ScreenerBatchBacktestConfigDialog(QtWidgets.QDialog):
    """批量回测参数确认。"""

    def __init__(
        self,
        *,
        class_names: list[str],
        default_class: str,
        default_start: str,
        default_end: str,
        count: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("批量回测")
        theme_manager().bind_stylesheet(self)
        self.class_name = default_class
        self.start_text = default_start
        self.end_text = default_end

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(f"将对勾选的 {count} 只股票逐只回测（不自动开始单页回测）。"))

        form = QtWidgets.QFormLayout()
        self.class_combo = QtWidgets.QComboBox()
        self.class_combo.addItems(class_names or [default_class])
        index = self.class_combo.findText(default_class)
        if index >= 0:
            self.class_combo.setCurrentIndex(index)
        form.addRow("策略", self.class_combo)

        self.start_edit = QtWidgets.QLineEdit(default_start)
        self.end_edit = QtWidgets.QLineEdit(default_end)
        form.addRow("开始日期", self.start_edit)
        form.addRow("结束日期", self.end_edit)
        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self.class_name = self.class_combo.currentText().strip()
        self.start_text = self.start_edit.text().strip()
        self.end_text = self.end_edit.text().strip()
        if not self.class_name:
            QtWidgets.QMessageBox.warning(self, "提示", "请选择策略")
            return
        self.accept()
