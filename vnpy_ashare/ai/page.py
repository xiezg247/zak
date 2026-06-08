"""AI 助手全屏页（左侧导航「AI 助手」）。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET
from vnpy_llm.engine import APP_NAME, LlmEngine
from vnpy_llm.ui.panel import AiChatPanel
from vnpy_llm.ui.session_widgets import AiSessionSidebar


class AiPageWidget(QtWidgets.QWidget):
    """左侧导航「AI 助手」全屏页。"""

    collapse_to_dock = QtCore.Signal()

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")

        engine = main_engine.get_engine(APP_NAME)
        if not isinstance(engine, LlmEngine):
            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(QtWidgets.QLabel("AI 引擎未加载"))
            self.panel = None
            return

        self._llm_engine = engine
        self.panel = AiChatPanel(engine, compact=False, parent=self)
        self.panel.collapse_requested.connect(self._on_collapse_requested)
        self.session_sidebar = AiSessionSidebar(engine, parent=self)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.session_sidebar)
        layout.addWidget(self.panel, stretch=1)
        self.setStyleSheet(TERMINAL_STYLESHEET)

    def _on_collapse_requested(self) -> None:
        self.collapse_to_dock.emit()

    def activate(self) -> None:
        if self.panel is not None:
            self.panel.focus_input()

    def deactivate(self) -> None:
        if self.panel is not None:
            self.panel.deactivate()
