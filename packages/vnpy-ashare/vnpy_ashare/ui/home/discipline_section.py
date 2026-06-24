"""Playbook 纪律卡片（checklist + 规则正文）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.playbook import DisciplineCheckItem, PlaybookSection
from vnpy_ashare.ui.home.discipline_panel import PlaybookDisciplinePanel


class PlaybookDisciplineCard(QtWidgets.QFrame):
    edit_requested = QtCore.Signal(str)
    checklist_changed = QtCore.Signal()
    discipline_ai_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeCardDiscipline")
        self._section_id = "discipline"
        self._collapsed = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        self._toggle = QtWidgets.QToolButton()
        self._toggle.setObjectName("HomeCardToggle")
        self._toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow)
        self._toggle.clicked.connect(self._on_toggle)

        self._num = QtWidgets.QLabel("5")
        self._num.setObjectName("HomeCardBadge")

        self._title = QtWidgets.QLabel("")
        self._title.setObjectName("HomeCardTitle")

        self._ai_btn = QtWidgets.QToolButton()
        self._ai_btn.setText("一句纪律")
        self._ai_btn.setObjectName("HomeCardAIBtn")
        self._ai_btn.setToolTip("结合 Playbook 与今日状态，请 AI 生成一句可执行纪律")
        self._ai_btn.clicked.connect(self.discipline_ai_requested.emit)

        self._edit = QtWidgets.QToolButton()
        self._edit.setText("编辑")
        self._edit.setObjectName("HomeCardAction")
        self._edit.clicked.connect(lambda: self.edit_requested.emit(self._section_id))

        header.addWidget(self._toggle)
        header.addWidget(self._num)
        header.addWidget(self._title, stretch=1)
        header.addWidget(self._ai_btn)
        header.addWidget(self._edit)

        self._discipline_panel = PlaybookDisciplinePanel(self)
        self._discipline_panel.changed.connect(self.checklist_changed.emit)

        self._rules = QtWidgets.QTextBrowser()
        self._rules.setObjectName("HomeCardBody")
        self._rules.setOpenExternalLinks(True)
        self._rules.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        root.addLayout(header)
        root.addWidget(self._discipline_panel)
        root.addWidget(self._rules)

    def apply(
        self,
        section: PlaybookSection,
        *,
        checklist: tuple[DisciplineCheckItem, ...],
        off_plan_symbols: tuple[str, ...],
        rules_html: str,
    ) -> None:
        self._section_id = section.section_id
        self._collapsed = section.collapsed
        self._title.setText(section.title)
        self._discipline_panel.apply(checklist, off_plan_symbols=off_plan_symbols)
        self._rules.setHtml(rules_html)
        self._sync_collapsed()

    def _sync_collapsed(self) -> None:
        visible = not self._collapsed
        self._discipline_panel.setVisible(visible)
        self._rules.setVisible(visible)
        self._toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow if self._collapsed else QtCore.Qt.ArrowType.DownArrow)

    def _on_toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._sync_collapsed()
        from vnpy_ashare.storage.repositories.trading_playbook import set_playbook_section_collapsed

        set_playbook_section_collapsed(self._section_id, self._collapsed)
