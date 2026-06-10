"""VeighNa App 菜单占位 Widget（实际 UI 在主窗口 Dock / 导航页）。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_llm.engine import APP_NAME, LlmEngine
from vnpy_llm.ui.panel import AiChatPanel


class LlmManagerWidget(QtWidgets.QWidget):
    """独立窗口打开时的 AI 助手页（与主窗口 Dock 共用引擎）。"""

    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        engine = main_engine.get_engine(APP_NAME)
        if not isinstance(engine, LlmEngine):
            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(QtWidgets.QLabel("AI 引擎未加载"))
            return

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(AiChatPanel(engine, compact=False, parent=self))
