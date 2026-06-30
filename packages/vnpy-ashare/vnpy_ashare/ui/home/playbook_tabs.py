"""Playbook Tab 布局：默认「买卖」一屏可见。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.playbook import PlaybookSection
from vnpy_ashare.services.trading_playbook import render_section_markdown
from vnpy_ashare.ui.home.execution_panel import PlaybookExecutionPanel
from vnpy_ashare.ui.home.playbook_discipline_tab import PlaybookDisciplineTab
from vnpy_ashare.ui.home.playbook_rules_panel import PlaybookRulesPanel
from vnpy_ashare.ui.home.timing_panel import PlaybookTimingPanel

_TAB_ORDER: tuple[tuple[str, str], ...] = (
    ("execution", "买卖"),
    ("timing", "择时"),
    ("universe", "选股"),
    ("risk", "风控"),
    ("discipline", "纪律"),
)

_RULES_TAB_SECTIONS: frozenset[str] = frozenset({"universe", "risk"})


class HomePlaybookTabs(QtWidgets.QWidget):
    discipline_ai_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePlaybookTabs")

        self._tabs = QtWidgets.QTabWidget(self)
        self._tabs.setObjectName("HomePlaybookTabBar")
        self._tabs.tabBar().setDrawBase(False)

        self._execution = PlaybookExecutionPanel()
        self._timing = PlaybookTimingPanel()
        self._rules_panels: dict[str, PlaybookRulesPanel] = {}
        self._discipline = PlaybookDisciplineTab()
        self._discipline.discipline_ai_requested.connect(self.discipline_ai_requested.emit)

        for section_id, label in _TAB_ORDER:
            if section_id == "execution":
                widget: QtWidgets.QWidget = self._execution
            elif section_id == "timing":
                widget = self._timing
            elif section_id == "discipline":
                widget = self._discipline
            elif section_id in _RULES_TAB_SECTIONS:
                panel = PlaybookRulesPanel()
                self._rules_panels[section_id] = panel
                widget = panel
            else:
                continue
            self._tabs.addTab(widget, label)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._tabs, stretch=1)

    def apply_sections(self, sections: tuple[PlaybookSection, ...]) -> None:
        by_id = {item.section_id: item for item in sections}

        execution = by_id.get("execution")
        if execution is not None:
            self._execution.apply_body(render_section_markdown(execution))

        timing = by_id.get("timing")
        if timing is not None:
            self._timing.apply_body(render_section_markdown(timing))

        for section_id, panel in self._rules_panels.items():
            section = by_id.get(section_id)
            if section is None:
                continue
            panel.apply_body(render_section_markdown(section))

        discipline = by_id.get("discipline")
        if discipline is not None:
            self._discipline.apply(discipline)
