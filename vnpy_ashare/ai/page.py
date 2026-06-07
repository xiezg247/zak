"""AI 助手全屏页。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET
from vnpy_llm.engine import APP_NAME, LlmEngine
from vnpy_llm.ui.panel import AiChatPanel


class AiPageWidget(QtWidgets.QWidget):
    """左侧导航「AI 助手」全屏页。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")

        engine = main_engine.get_engine(APP_NAME)
        if not isinstance(engine, LlmEngine):
            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(QtWidgets.QLabel("AI 引擎未加载"))
            return

        self._llm_engine = engine
        self.panel = AiChatPanel(engine, compact=False, parent=self)
        self.panel.collapse_requested.connect(self._on_collapse_requested)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)
        self.setStyleSheet(TERMINAL_STYLESHEET)

    collapse_to_dock = QtCore.Signal()

    def _on_collapse_requested(self) -> None:
        self.collapse_to_dock.emit()

    def activate(self) -> None:
        self.panel.focus_input()

    def deactivate(self) -> None:
        self.panel.deactivate()
