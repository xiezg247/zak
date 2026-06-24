"""Playbook 单章卡片。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.playbook import PlaybookSection
from vnpy_llm.ui.panel.md_renderer import render_markdown

_SECTION_NUMBERS: dict[str, int] = {
    "timing": 1,
    "universe": 2,
    "execution": 3,
    "risk": 4,
    "discipline": 5,
}


class PlaybookSectionCard(QtWidgets.QFrame):
    edit_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeCard")
        self._section_id = ""
        self._collapsed = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        self._toggle = QtWidgets.QToolButton()
        self._toggle.setObjectName("HomeCardToggle")
        self._toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow)
        self._toggle.clicked.connect(self._on_toggle)

        self._num = QtWidgets.QLabel("")
        self._num.setObjectName("HomeCardBadge")
        self._num.hide()

        self._title = QtWidgets.QLabel("")
        self._title.setObjectName("HomeCardTitle")

        self._edit = QtWidgets.QToolButton()
        self._edit.setText("编辑")
        self._edit.setObjectName("HomeCardAction")
        self._edit.clicked.connect(lambda: self.edit_requested.emit(self._section_id))

        header.addWidget(self._toggle)
        header.addWidget(self._num)
        header.addWidget(self._title, stretch=1)
        header.addWidget(self._edit)

        self._body = QtWidgets.QTextBrowser()
        self._body.setObjectName("HomeCardBody")
        self._body.setOpenExternalLinks(True)
        self._body.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        root.addLayout(header)
        root.addWidget(self._body)

    def apply(self, section: PlaybookSection, *, body_html: str) -> None:
        self._section_id = section.section_id
        self._collapsed = section.collapsed
        num = _SECTION_NUMBERS.get(section.section_id, 0)
        if num:
            self._num.setText(str(num))
            self._num.show()
        else:
            self._num.hide()
        self._title.setText(section.title)
        self._body.setHtml(body_html)
        self._sync_collapsed()

    def _sync_collapsed(self) -> None:
        self._body.setVisible(not self._collapsed)
        self._toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow if self._collapsed else QtCore.Qt.ArrowType.DownArrow)

    def _on_toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._sync_collapsed()
        if self._section_id:
            from vnpy_ashare.storage.repositories.trading_playbook import set_playbook_section_collapsed

            set_playbook_section_collapsed(self._section_id, self._collapsed)

    @staticmethod
    def render_html(markdown: str) -> str:
        return str(render_markdown(markdown))
