"""Playbook 章节编辑对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.trading.playbook import PlaybookSectionUpdate
from vnpy_ashare.services.trading_playbook import save_playbook_section_body
from vnpy_common.ui.dialog_shell import setup_responsive_dialog


def edit_playbook_section_dialog(
    *,
    section_id: str,
    title: str,
    body_md: str,
    parent: QtWidgets.QWidget | None = None,
) -> str | None:
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(f"编辑 · {title}")
    setup_responsive_dialog(dialog, parent, min_width=640, min_height=480)

    editor = QtWidgets.QPlainTextEdit(dialog)
    editor.setPlainText(body_md)
    editor.setTabStopDistance(24)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
    )
    saved: list[str | None] = [None]

    def on_save() -> None:
        text = editor.toPlainText().strip()
        save_playbook_section_body(section_id, PlaybookSectionUpdate(body_md=text))
        saved[0] = text
        dialog.accept()

    buttons.accepted.connect(on_save)
    buttons.rejected.connect(dialog.reject)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(editor)
    layout.addWidget(buttons)

    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return saved[0]
