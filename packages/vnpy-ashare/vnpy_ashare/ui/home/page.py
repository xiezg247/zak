"""Playbook 首屏：交易体系与规则。"""

from __future__ import annotations

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions
from vnpy_ashare.ai.context.playbook import build_discipline_one_liner_prompt, build_playbook_extra
from vnpy_ashare.ai.context.store import set_ai_context
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.trading.playbook import PlaybookSection
from vnpy_ashare.services.trading_playbook import (
    build_home_playbook_status,
    load_discipline_checklist,
    load_playbook_sections,
    render_section_markdown,
)
from vnpy_ashare.ui.home.discipline_section import PlaybookDisciplineCard
from vnpy_ashare.ui.home.section_view import PlaybookSectionCard
from vnpy_ashare.ui.home.status_strip import HomePlaybookStatusStrip
from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_worker import EmotionCycleLoadWorker
from vnpy_common.ai.protocol import AiContextData
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active
from vnpy_common.ui.theme.build_extra import build_home_playbook_stylesheet
from vnpy_common.ui.theme.manager import theme_manager

_GRID_COLS = 3

_CARD_LAYOUT: dict[str, tuple[int, int, int, int]] = {
    "timing": (0, 0, 1, 1),
    "universe": (0, 1, 1, 1),
    "execution": (0, 2, 1, 1),
    "risk": (1, 0, 1, 1),
    "discipline": (1, 1, 1, 2),
}


class HomePageWidget(QtWidgets.QWidget):
    """个人交易体系 Playbook；activate 不发起行情网络请求。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("HomeRoot")

        self._sections: dict[str, PlaybookSection] = {}
        self._card_views: dict[str, QtWidgets.QWidget] = {}
        self._emotion_worker: QtCore.QThread | None = None
        self._retired_emotion_workers: list[QtCore.QThread] = []
        self._last_status = build_home_playbook_status(main_engine)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("HomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QtWidgets.QWidget()
        body.setObjectName("HomeBody")
        root = QtWidgets.QVBoxLayout(body)
        root.setContentsMargins(20, 24, 20, 32)
        root.setSpacing(16)

        self._title = QtWidgets.QLabel("今日守则")
        self._title.setObjectName("HomePageTitle")
        self._subtitle = QtWidgets.QLabel("")
        self._subtitle.setObjectName("HomePageSubtitle")
        root.addWidget(self._title)
        root.addWidget(self._subtitle)

        self._status_strip = HomePlaybookStatusStrip(body)
        root.addWidget(self._status_strip)

        self._cards_container = QtWidgets.QWidget()
        self._cards_grid = QtWidgets.QGridLayout(self._cards_container)
        self._cards_grid.setContentsMargins(0, 0, 0, 0)
        self._cards_grid.setHorizontalSpacing(12)
        self._cards_grid.setVerticalSpacing(12)
        root.addWidget(self._cards_container)
        root.addStretch(1)

        scroll.setWidget(body)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        theme_manager().bind_stylesheet(self, extra=build_home_playbook_stylesheet)
        self._rebuild_cards()
        self._apply_header(self._last_status)
        self._status_strip.apply(self._last_status)

    def activate(self) -> None:
        self._refresh_status()
        self._maybe_refresh_emotion_async()

    def deactivate(self) -> None:
        worker = self._emotion_worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
        self._emotion_worker = None

    def _apply_header(self, status) -> None:
        self._subtitle.setText(f"{status.profile_title}　·　{status.phase_label}")

    def _refresh_status(self) -> None:
        self._last_status = build_home_playbook_status(self.main_engine)
        self._apply_header(self._last_status)
        self._status_strip.apply(self._last_status)
        set_ai_context(
            enrich_context_with_actions(
                AiContextData(page="守则", extra=build_playbook_extra(self._last_status)),
            ),
        )
        self._reload_cards_if_needed()

    def _maybe_refresh_emotion_async(self) -> None:
        if self._last_status.emotion_label != "—":
            return
        if thread_is_active(self._emotion_worker):
            return
        self._status_strip.set_emotion_loading(True)
        worker = EmotionCycleLoadWorker(self)
        self._emotion_worker = worker

        def on_finished(_snapshot: object, *, _worker: QtCore.QThread = worker) -> None:
            if self._emotion_worker is _worker:
                self._emotion_worker = None
            release_thread(self._retired_emotion_workers, _worker)
            self._status_strip.set_emotion_loading(False)
            self._refresh_status()

        worker.finished.connect(on_finished)
        worker.start()

    def _reload_cards_if_needed(self) -> None:
        sections = load_playbook_sections()
        if {item.section_id for item in sections} != set(self._sections):
            self._rebuild_cards()
            return
        for section in sections:
            self._sections[section.section_id] = section
            self._apply_card(section)

    def _apply_card(self, section: PlaybookSection) -> None:
        widget = self._card_views.get(section.section_id)
        if widget is None:
            return
        if section.section_id == "discipline" and isinstance(widget, PlaybookDisciplineCard):
            widget.apply(
                section,
                checklist=load_discipline_checklist(),
                off_plan_symbols=self._last_status.off_plan_symbols,
                rules_html=PlaybookSectionCard.render_html(section.body_md.strip()),
            )
            return
        if isinstance(widget, PlaybookSectionCard):
            markdown = render_section_markdown(section)
            widget.apply(section, body_html=PlaybookSectionCard.render_html(markdown))

    def _rebuild_cards(self) -> None:
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._sections.clear()
        self._card_views.clear()

        for section in load_playbook_sections():
            self._sections[section.section_id] = section
            view: QtWidgets.QWidget
            if section.section_id == "discipline":
                discipline_view = PlaybookDisciplineCard(self._cards_container)
                discipline_view.checklist_changed.connect(self._on_discipline_changed)
                discipline_view.discipline_ai_requested.connect(self._on_discipline_ai)
                view = discipline_view
            else:
                section_view = PlaybookSectionCard(self._cards_container)
                view = section_view
            self._card_views[section.section_id] = view
            row, col, rspan, cspan = _CARD_LAYOUT.get(section.section_id, (0, 0, 1, 1))
            self._cards_grid.addWidget(view, row, col, rspan, cspan)
            self._apply_card(section)

        for col in range(_GRID_COLS):
            self._cards_grid.setColumnStretch(col, 1)

    def _on_discipline_changed(self) -> None:
        self._last_status = build_home_playbook_status(self.main_engine)
        self._status_strip.apply(self._last_status)
        section = self._sections.get("discipline")
        widget = self._card_views.get("discipline")
        if section is not None and isinstance(widget, PlaybookDisciplineCard):
            widget.apply(
                section,
                checklist=load_discipline_checklist(),
                off_plan_symbols=self._last_status.off_plan_symbols,
                rules_html=PlaybookSectionCard.render_html(section.body_md.strip()),
            )

    def _on_discipline_ai(self) -> None:
        self.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=build_discipline_one_liner_prompt(),
                    source_page="守则",
                ),
            ),
        )
