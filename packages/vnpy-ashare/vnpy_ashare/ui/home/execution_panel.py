"""Playbook §3 买卖：紧凑表格。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.home.playbook_rules_panel import PlaybookRulesPanel


class PlaybookExecutionPanel(PlaybookRulesPanel):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybookExecutionPanel")
