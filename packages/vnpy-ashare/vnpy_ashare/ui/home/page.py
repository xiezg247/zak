"""Playbook 首屏：交易体系与规则。"""

from __future__ import annotations

from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions
from vnpy_ashare.ai.context.playbook import build_discipline_one_liner_prompt, build_playbook_extra
from vnpy_ashare.ai.context.store import set_ai_context
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets
from vnpy_common.ai.protocol import AiContextData

from vnpy_ashare.domain.trading.playbook import PlaybookSection
from vnpy_ashare.services.trading_playbook import (
    build_home_playbook_status,
    load_discipline_checklist,
    load_playbook_sections,
    render_section_markdown,
)
from vnpy_ashare.ui.home.discipline_section import PlaybookDisciplineSectionView
from vnpy_ashare.ui.home.editor_dialog import edit_playbook_section_dialog
from vnpy_ashare.ui.home.section_view import PlaybookSectionView
from vnpy_ashare.ui.home.status_strip import HomePlaybookStatusStrip
from vnpy_common.ui.theme.manager import theme_manager


class HomePageWidget(QtWidgets.QWidget):
    """个人交易体系 Playbook；activate 不发起行情网络请求。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("HomeRoot")

        self._sections: dict[str, PlaybookSection] = {}
        self._section_views: dict[str, QtWidgets.QWidget] = {}
        self._last_status = build_home_playbook_status(main_engine)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("HomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        body = QtWidgets.QWidget()
        body.setObjectName("HomeBody")
        root = QtWidgets.QVBoxLayout(body)
        root.setContentsMargins(20, 20, 20, 28)
        root.setSpacing(14)

        header = QtWidgets.QHBoxLayout()
        self._title = QtWidgets.QLabel("我的交易体系")
        self._title.setObjectName("HomeTitle")
        self._subtitle = QtWidgets.QLabel("")
        self._subtitle.setObjectName("HomePhaseLabel")
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._subtitle)
        root.addLayout(header)

        self._status_strip = HomePlaybookStatusStrip(body)
        root.addWidget(self._status_strip)

        self._sections_container = QtWidgets.QWidget()
        self._sections_host = QtWidgets.QVBoxLayout(self._sections_container)
        self._sections_host.setContentsMargins(0, 0, 0, 0)
        self._sections_host.setSpacing(10)
        root.addWidget(self._sections_container)
        root.addStretch(1)

        scroll.setWidget(body)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        theme_manager().bind_stylesheet(self)
        self._rebuild_sections()

    def activate(self) -> None:
        self._last_status = build_home_playbook_status(self.main_engine)
        self._title.setText(f"我的交易体系 · {self._last_status.profile_title}")
        self._subtitle.setText(self._last_status.phase_label)
        self._status_strip.apply(self._last_status)
        set_ai_context(
            enrich_context_with_actions(
                AiContextData(page="交易体系", extra=build_playbook_extra(self._last_status)),
            ),
        )
        self._reload_sections_if_needed()

    def deactivate(self) -> None:
        pass

    def _reload_sections_if_needed(self) -> None:
        sections = load_playbook_sections()
        if {item.section_id for item in sections} != set(self._sections):
            self._rebuild_sections()
            return
        for section in sections:
            self._sections[section.section_id] = section
            self._apply_section_widget(section)

    def _apply_section_widget(self, section: PlaybookSection) -> None:
        widget = self._section_views.get(section.section_id)
        if widget is None:
            return
        if section.section_id == "discipline" and isinstance(widget, PlaybookDisciplineSectionView):
            widget.apply(
                section,
                checklist=load_discipline_checklist(),
                off_plan_symbols=self._last_status.off_plan_symbols,
                rules_html=PlaybookSectionView.render_html(section.body_md.strip()),
            )
            return
        if isinstance(widget, PlaybookSectionView):
            markdown = render_section_markdown(section)
            widget.apply(section, body_html=PlaybookSectionView.render_html(markdown))

    def _rebuild_sections(self) -> None:
        while self._sections_host.count():
            item = self._sections_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._sections.clear()
        self._section_views.clear()

        for section in load_playbook_sections():
            self._sections[section.section_id] = section
            if section.section_id == "discipline":
                view: QtWidgets.QWidget = PlaybookDisciplineSectionView(self._sections_container)
                view.edit_requested.connect(self._on_edit_section)
                view.checklist_changed.connect(self._on_discipline_changed)
                view.discipline_ai_requested.connect(self._on_discipline_ai)
            else:
                view = PlaybookSectionView(self._sections_container)
                view.edit_requested.connect(self._on_edit_section)
            self._section_views[section.section_id] = view
            self._sections_host.addWidget(view)
            self._apply_section_widget(section)

    def _on_discipline_changed(self) -> None:
        self._last_status = build_home_playbook_status(self.main_engine)
        self._status_strip.apply(self._last_status)
        section = self._sections.get("discipline")
        widget = self._section_views.get("discipline")
        if section is not None and isinstance(widget, PlaybookDisciplineSectionView):
            widget.apply(
                section,
                checklist=load_discipline_checklist(),
                off_plan_symbols=self._last_status.off_plan_symbols,
                rules_html=PlaybookSectionView.render_html(section.body_md.strip()),
            )

    def _on_discipline_ai(self) -> None:
        self.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=build_discipline_one_liner_prompt(),
                    source_page="交易体系",
                ),
            ),
        )

    def _on_edit_section(self, section_id: str) -> None:
        section = self._sections.get(section_id)
        if section is None:
            return
        edited = edit_playbook_section_dialog(
            section_id=section_id,
            title=section.title,
            body_md=section.body_md,
            parent=self,
        )
        if edited is None:
            return
        updated = PlaybookSection(
            section_id=section.section_id,
            title=section.title,
            body_md=edited,
            collapsed=section.collapsed,
            sort_order=section.sort_order,
        )
        self._sections[section_id] = updated
        self._apply_section_widget(updated)
