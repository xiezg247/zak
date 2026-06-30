"""Playbook 纪律 Tab：规则表格。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.playbook import PlaybookSection
from vnpy_ashare.ui.home.playbook_rules_panel import PlaybookRulesPanel


class PlaybookDisciplineTab(QtWidgets.QWidget):
    discipline_ai_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybookDisciplineTab")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.addStretch(1)
        self._ai_btn = QtWidgets.QToolButton()
        self._ai_btn.setText("一句纪律")
        self._ai_btn.setObjectName("HomeCardAIBtn")
        self._ai_btn.setToolTip("结合 Playbook 与今日状态，请 AI 生成一句可执行纪律")
        self._ai_btn.clicked.connect(self.discipline_ai_requested.emit)
        header.addWidget(self._ai_btn)
        root.addLayout(header)

        self._rules = PlaybookRulesPanel(self)
        root.addWidget(self._rules, stretch=1)

    def apply(self, section: PlaybookSection) -> None:
        self._rules.apply_body(section.body_md.strip())
