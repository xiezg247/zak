"""Playbook 单章视图。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.playbook import PlaybookSection
from vnpy_llm.ui.panel.md_renderer import render_markdown


class PlaybookSectionView(QtWidgets.QWidget):
    edit_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._section_id = ""
        self._collapsed = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 8)
        self._toggle = QtWidgets.QToolButton()
        self._toggle.setObjectName("PlaybookSectionToggle")
        self._toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow)
        self._toggle.clicked.connect(self._on_toggle)

        self._title = QtWidgets.QLabel("")
        self._title.setObjectName("HomeTitle")

        self._edit_btn = QtWidgets.QToolButton()
        self._edit_btn.setText("编辑")
        self._edit_btn.setObjectName("SecondaryButton")
        self._edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._section_id))

        header.addWidget(self._toggle)
        header.addWidget(self._title, stretch=1)
        header.addWidget(self._edit_btn)

        self._header_host = QtWidgets.QWidget()
        self._header_host.setObjectName("PlaybookSectionHeader")
        self._header_host.setLayout(header)

        self._body = QtWidgets.QTextBrowser()
        self._body.setObjectName("PlaybookSectionBody")
        self._body.setOpenExternalLinks(True)
        self._body.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        root.addWidget(self._header_host)
        root.addWidget(self._body)

    def apply(self, section: PlaybookSection, *, body_html: str) -> None:
        self._section_id = section.section_id
        self._collapsed = section.collapsed
        self._title.setText(section.title)
        self._body.setHtml(body_html)
        self._sync_collapsed()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._sync_collapsed()

    def _sync_collapsed(self) -> None:
        self._body.setVisible(not self._collapsed)
        self._toggle.setArrowType(
            QtCore.Qt.ArrowType.RightArrow if self._collapsed else QtCore.Qt.ArrowType.DownArrow
        )

    def _on_toggle(self) -> None:
        self.set_collapsed(not self._collapsed)
        if self._section_id:
            from vnpy_ashare.storage.repositories.trading_playbook import set_playbook_section_collapsed

            set_playbook_section_collapsed(self._section_id, self._collapsed)

    @staticmethod
    def render_html(markdown: str) -> str:
        return render_markdown(markdown)
