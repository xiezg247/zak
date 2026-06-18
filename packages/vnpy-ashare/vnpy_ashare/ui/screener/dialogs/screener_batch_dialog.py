"""选股批量回测结果对话框。"""

from __future__ import annotations

from datetime import datetime, timedelta

from vnpy.trader.constant import Interval
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.backtest.batch_templates import (
    format_batch_backtest_template_note,
    get_batch_backtest_template,
    list_batch_backtest_template_choices,
)
from vnpy_ashare.screener.batch.batch_actions import BatchBacktestRow, export_batch_backtest_rows_to_csv
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.theme.manager import theme_manager


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
        export_batch_backtest_rows_to_csv(self._rows, path)
        page_notify(self, f"已导出：{path}", level="success")


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
        template_note: str = "",
        default_template_id: str = "",
        auto_template_id: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("批量回测")
        theme_manager().bind_stylesheet(self)
        self.class_name = default_class
        self.start_text = default_start
        self.end_text = default_end
        self.template_id = (default_template_id or "").strip()
        self._auto_template_id = (auto_template_id or "").strip()
        self._class_names = class_names or [default_class]
        self._default_end = default_end
        self._initial_class = default_class
        self._initial_start = default_start
        self._initial_end = default_end

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(f"将对勾选的 {count} 只股票逐只回测（不自动开始单页回测）。"))

        self._template_hint = QtWidgets.QLabel("")
        self._template_hint.setObjectName("SecondaryLabel")
        self._template_hint.setWordWrap(True)
        layout.addWidget(self._template_hint)

        form = QtWidgets.QFormLayout()
        self.template_combo = QtWidgets.QComboBox()
        self._template_ids: list[str] = []
        for template_id, label in list_batch_backtest_template_choices():
            self._template_ids.append(template_id)
            self.template_combo.addItem(label, template_id)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        form.addRow("回测模板", self.template_combo)

        self.class_combo = QtWidgets.QComboBox()
        self.class_combo.addItems(self._class_names)
        self._set_class_combo(default_class)
        form.addRow("策略", self.class_combo)

        self.start_edit = QtWidgets.QLineEdit(default_start)
        self.end_edit = QtWidgets.QLineEdit(default_end)
        form.addRow("开始日期", self.start_edit)
        form.addRow("结束日期", self.end_edit)
        layout.addLayout(form)

        self._set_template_selection(self.template_id)
        if not self.template_id and template_note.strip():
            self._update_template_hint(template_note.strip())

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_template_selection(self, template_id: str) -> None:
        tid = (template_id or "").strip()
        for index, candidate in enumerate(self._template_ids):
            if candidate == tid:
                self.template_combo.blockSignals(True)
                self.template_combo.setCurrentIndex(index)
                self.template_combo.blockSignals(False)
                self._apply_template_preview(tid)
                return
        self.template_combo.blockSignals(True)
        self.template_combo.setCurrentIndex(0)
        self.template_combo.blockSignals(False)

    def _on_template_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._template_ids):
            return
        self._apply_template_preview(self._template_ids[index])

    def _apply_template_preview(self, template_id: str) -> None:
        tid = (template_id or "").strip()
        self.template_id = tid
        if not tid:
            auto_note = format_batch_backtest_template_note(self._auto_template_id)
            if auto_note:
                self._update_template_hint(f"自动：{auto_note}")
            else:
                self._update_template_hint("自动：未匹配来源模板，使用下方策略与日期")
            self._set_class_combo(self._initial_class)
            self.start_edit.setText(self._initial_start)
            self.end_edit.setText(self._initial_end)
            return

        template = get_batch_backtest_template(tid)
        if template is None:
            self._update_template_hint("")
            return

        end_text = self.end_edit.text().strip() or self._default_end
        try:
            end = datetime.strptime(end_text[:10], "%Y-%m-%d")
        except ValueError:
            end = datetime.strptime(self._default_end[:10], "%Y-%m-%d")
        start = end - timedelta(days=template.lookback_days)
        if start > end:
            start = end

        self._set_class_combo(template.class_name)
        self.start_edit.setText(start.strftime("%Y-%m-%d"))
        self.end_edit.setText(end.strftime("%Y-%m-%d"))
        self._update_template_hint(format_batch_backtest_template_note(tid))

    def _set_class_combo(self, class_name: str) -> None:
        index = self.class_combo.findText(class_name)
        if index >= 0:
            self.class_combo.setCurrentIndex(index)
            return
        self.class_combo.addItem(class_name)
        self.class_combo.setCurrentIndex(self.class_combo.count() - 1)

    def _update_template_hint(self, text: str) -> None:
        if text.strip():
            self._template_hint.setText(f"模板：{text.strip()}")
            self._template_hint.setVisible(True)
        else:
            self._template_hint.clear()
            self._template_hint.setVisible(False)

    def _accept(self) -> None:
        self.class_name = self.class_combo.currentText().strip()
        self.start_text = self.start_edit.text().strip()
        self.end_text = self.end_edit.text().strip()
        if not self.class_name:
            page_notify(self, "请选择策略", level="warning")
            return

        tid = (self.template_id or "").strip()
        template = get_batch_backtest_template(tid) if tid else None
        if template is not None and template.interval == Interval.MINUTE:
            reply = QtWidgets.QMessageBox.question(
                self,
                "分 K 回测",
                "分 K 模板需要本地 1 分钟 K 线数据；缺失时单只结果会标记错误。\n是否继续？",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.accept()
