"""保存个股分析报告对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_common.ui.dialog_shell import apply_standard_dialog_layout, setup_responsive_dialog
from vnpy_common.ui.theme import theme_manager


class SaveAnalysisReportDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        default_title: str,
        default_body: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SaveAnalysisReportDialog")
        self.setWindowTitle("保存分析报告")
        setup_responsive_dialog(
            self,
            parent,
            min_width=720,
            min_height=520,
            width_ratio=0.62,
            height_ratio=0.72,
            max_width=960,
            max_height=760,
        )

        title_label = QtWidgets.QLabel("标题", self)
        self._title_edit = QtWidgets.QLineEdit(self)
        self._title_edit.setText(default_title.strip())

        body_label = QtWidgets.QLabel("正文（Markdown）", self)
        self._body_edit = QtWidgets.QPlainTextEdit(self)
        self._body_edit.setPlainText(default_body)

        form = QtWidgets.QFormLayout()
        form.addRow(title_label, self._title_edit)
        form.addRow(body_label, self._body_edit)

        save_btn = QtWidgets.QPushButton("保存", self)
        save_btn.setObjectName("ActionButton")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("取消", self)
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)

        content = QtWidgets.QWidget(self)
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addLayout(form)
        content_layout.addLayout(footer)

        apply_standard_dialog_layout(self, content=content, margins=(16, 14, 16, 12))
        theme_manager().bind_stylesheet(self)

    def title_text(self) -> str:
        return self._title_edit.text().strip()

    def body_text(self) -> str:
        return self._body_edit.toPlainText().strip()
