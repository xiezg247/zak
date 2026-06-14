"""分析报告 Tab：历史列表 + Markdown 预览。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.stock_note import StockAnalysisReport
from vnpy_ashare.ui.markdown_render import render_markdown_html
from vnpy_common.ui.theme import theme_manager

_REPORT_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole


class NotesCenterReportsView(QtWidgets.QWidget):
    report_delete_requested = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NotesCenterReportsView")

        self._list = QtWidgets.QListWidget(self)
        self._list.setObjectName("NotesCenterReportsList")
        self._list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._list.currentItemChanged.connect(self._on_report_selected)

        self._preview = QtWidgets.QTextBrowser(self)
        self._preview.setObjectName("NotesCenterReportPreview")
        self._preview.setOpenExternalLinks(True)

        self._delete_button = QtWidgets.QPushButton("删除报告", self)
        self._delete_button.setObjectName("SecondaryButton")
        self._delete_button.clicked.connect(self._delete_current)

        self._empty_label = QtWidgets.QLabel("暂无分析报告", self)
        self._empty_label.setObjectName("PanelHint")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        list_panel = QtWidgets.QWidget(self)
        list_layout = QtWidgets.QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self._list, stretch=1)
        list_layout.addWidget(self._empty_label)

        preview_panel = QtWidgets.QWidget(self)
        preview_layout = QtWidgets.QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(6)
        preview_layout.addWidget(self._preview, stretch=1)
        preview_layout.addWidget(self._delete_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.addWidget(list_panel)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 520])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._reports: list[StockAnalysisReport] = []
        theme_manager().bind_stylesheet(self)
        theme_manager().register_callback(self._refresh_preview_theme)

    def load_reports(self, reports: list[StockAnalysisReport]) -> None:
        self._reports = list(reports)
        self._list.blockSignals(True)
        self._list.clear()
        for report in reports:
            item = QtWidgets.QListWidgetItem(_format_report_item(report))
            item.setData(_REPORT_ID_ROLE, report.id)
            item.setToolTip(report.summary or report.title)
            self._list.addItem(item)
        self._list.blockSignals(False)
        has_items = self._list.count() > 0
        self._list.setVisible(has_items)
        self._empty_label.setVisible(not has_items)
        self._delete_button.setEnabled(False)
        if has_items:
            self._list.setCurrentRow(0)
        else:
            self._preview.clear()

    def clear(self) -> None:
        self.load_reports([])

    def remove_report_id(self, report_id: int) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None and item.data(_REPORT_ID_ROLE) == report_id:
                self._list.takeItem(index)
                break
        self._reports = [report for report in self._reports if report.id != report_id]
        has_items = self._list.count() > 0
        self._list.setVisible(has_items)
        self._empty_label.setVisible(not has_items)
        if not has_items:
            self._preview.clear()
            self._delete_button.setEnabled(False)

    def _on_report_selected(
        self,
        current: QtWidgets.QListWidgetItem | None,
        _previous: QtWidgets.QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._preview.clear()
            self._delete_button.setEnabled(False)
            return
        report_id = current.data(_REPORT_ID_ROLE)
        report = next((item for item in self._reports if item.id == report_id), None)
        if report is None:
            self._preview.clear()
            self._delete_button.setEnabled(False)
            return
        self._preview.setHtml(render_markdown_html(report.body))
        self._delete_button.setEnabled(True)

    def _refresh_preview_theme(self) -> None:
        current = self._list.currentItem()
        if current is None:
            return
        self._on_report_selected(current, None)

    def _delete_current(self) -> None:
        current = self._list.currentItem()
        if current is None:
            return
        report_id = current.data(_REPORT_ID_ROLE)
        if report_id is None:
            return
        self.report_delete_requested.emit(int(report_id))


def _format_report_item(report: StockAnalysisReport) -> str:
    time_label = report.created_at.replace("T", " ")[:16]
    scope = f" · {report.source_scope}" if report.source_scope else ""
    return f"{time_label}{scope}\n{report.title}"
