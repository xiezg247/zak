"""Playbook 通用规则面板：紧凑表格 + 补充说明。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.home.playbook_markdown_tables import parse_playbook_table_blocks
from vnpy_ashare.ui.home.playbook_rule_table import PlaybookRuleTable
from vnpy_ashare.ui.home.section_view import PlaybookSectionCard


def extract_playbook_note_lines(body_md: str) -> str:
    notes: list[str] = []
    for line in body_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("|"):
            notes.append(stripped[2:].strip())
    return "\n".join(notes)


class PlaybookRulesPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybookRulesPanel")

        self._tables_host = QtWidgets.QWidget(self)
        self._tables_layout = QtWidgets.QVBoxLayout(self._tables_host)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._tables_layout.setSpacing(12)
        self._tables: list[PlaybookRuleTable] = []

        self._note = QtWidgets.QLabel("")
        self._note.setObjectName("PlaybookRulesNote")
        self._note.setWordWrap(True)
        self._note.hide()

        self._fallback = QtWidgets.QTextBrowser()
        self._fallback.setObjectName("HomeCardBody")
        self._fallback.setOpenExternalLinks(True)
        self._fallback.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._fallback.hide()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._tables_host, stretch=1)
        root.addWidget(self._note)
        root.addWidget(self._fallback, stretch=1)

    def apply_body(self, body_md: str) -> None:
        blocks = parse_playbook_table_blocks(body_md)
        if blocks:
            self._fallback.hide()
            self._tables_host.show()
            while len(self._tables) < len(blocks):
                table = PlaybookRuleTable(self._tables_host)
                self._tables_layout.addWidget(table)
                self._tables.append(table)
            for index, block in enumerate(blocks):
                self._tables[index].apply_block(block)
                self._tables[index].show()
            for index in range(len(blocks), len(self._tables)):
                self._tables[index].hide()
            note_text = extract_playbook_note_lines(body_md)
            if note_text:
                self._note.setText(note_text)
                self._note.show()
            else:
                self._note.hide()
            return

        self._tables_host.hide()
        self._note.hide()
        self._fallback.setHtml(PlaybookSectionCard.render_html(body_md))
        self._fallback.show()
