"""Playbook 首屏：交易体系与规则。"""

from __future__ import annotations

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions
from vnpy_ashare.ai.context.playbook import build_discipline_one_liner_prompt, build_playbook_extra
from vnpy_ashare.ai.context.store import set_ai_context
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.config.preferences.strategy_profile import get_strategy_profile, load_strategy_profile_id
from vnpy_ashare.services.trading_playbook import build_home_playbook_status, load_playbook_sections
from vnpy_ashare.ui.home.playbook_tabs import HomePlaybookTabs
from vnpy_common.ai.protocol import AiContextData
from vnpy_common.ui.theme.build_extra import build_home_playbook_stylesheet
from vnpy_common.ui.theme.manager import theme_manager


class HomePageWidget(QtWidgets.QWidget):
    """个人交易体系 Playbook；activate 不发起行情网络请求。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("HomeRoot")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 24, 20, 20)
        root.setSpacing(12)

        self._title = QtWidgets.QLabel("今日守则")
        self._title.setObjectName("HomePageTitle")
        self._subtitle = QtWidgets.QLabel("")
        self._subtitle.setObjectName("HomePageSubtitle")
        root.addWidget(self._title)
        root.addWidget(self._subtitle)

        self._tabs = HomePlaybookTabs(self)
        self._tabs.discipline_ai_requested.connect(self._on_discipline_ai)
        root.addWidget(self._tabs, stretch=1)

        theme_manager().bind_stylesheet(self, extra=build_home_playbook_stylesheet)
        self._apply_header()
        self._reload_content()

    def activate(self) -> None:
        self._refresh_ai_context()

    def deactivate(self) -> None:
        return

    def _apply_header(self) -> None:
        profile = get_strategy_profile(load_strategy_profile_id())
        self._subtitle.setText(profile.title)

    def _refresh_ai_context(self) -> None:
        status = build_home_playbook_status(self.main_engine)
        set_ai_context(
            enrich_context_with_actions(
                AiContextData(page="守则", extra=build_playbook_extra(status)),
            ),
        )

    def _reload_content(self) -> None:
        self._tabs.apply_sections(load_playbook_sections())

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
