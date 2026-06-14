"""个股分析内嵌 AI 侧栏。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.theme import theme_manager
from vnpy_llm.ui.panel.chat import AiChatPanel
from vnpy_llm.ui.themed_styles import bind_ai_panel_style

if TYPE_CHECKING:
    from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
    from vnpy_llm.app.engine import LlmEngine

_DEFAULT_WIDTH = 380
_MIN_WIDTH = 320


class StockAnalysisAiSidebar(QtWidgets.QWidget):
    """个股分析右侧可折叠 AI 对话侧栏。"""

    collapsed = QtCore.Signal()

    def __init__(self, host: StockAnalysisHost, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StockAnalysisAiSidebar")
        self._host = host
        self._engine: LlmEngine | None = None
        self._panel: AiChatPanel | None = None
        self._splitter: QtWidgets.QSplitter | None = None
        self._expanded = False
        self.setMinimumWidth(0)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(8, 6, 8, 4)
        title = QtWidgets.QLabel("AI 解读")
        title.setObjectName("StockAnalysisAiTitle")
        header.addWidget(title)
        header.addStretch()
        collapse_btn = QtWidgets.QPushButton("收起")
        collapse_btn.setObjectName("SecondaryButton")
        collapse_btn.setFlat(True)
        collapse_btn.clicked.connect(self.collapse)
        header.addWidget(collapse_btn)

        self._placeholder = QtWidgets.QLabel("AI 引擎未加载，请检查 LLM 配置。")
        self._placeholder.setObjectName("StockAnalysisAiPlaceholder")
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._chat_host = QtWidgets.QWidget()
        self._chat_host.setObjectName("StockAnalysisAiChatHost")
        self._chat_layout = QtWidgets.QVBoxLayout(self._chat_host)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self._placeholder, stretch=1)
        layout.addWidget(self._chat_host, stretch=1)
        self._chat_host.hide()

        theme_manager().register_callback(lambda _tokens: self._on_theme_changed())

    def attach_splitter(self, splitter: QtWidgets.QSplitter) -> None:
        self._splitter = splitter

    def bind_engine(self, engine: LlmEngine | None) -> bool:
        if engine is None:
            return False
        if self._panel is not None:
            return True
        self._engine = engine
        panel = AiChatPanel(engine, compact=True, parent=self._chat_host)
        panel.expand_requested.connect(self._open_full_ai_page)
        bind_ai_panel_style(panel)
        self._panel = panel
        self._chat_layout.addWidget(panel)
        self._placeholder.hide()
        self._chat_host.show()
        return True

    def is_expanded(self) -> bool:
        return self._expanded

    def expand(self, width: int = _DEFAULT_WIDTH) -> None:
        if self._panel is None:
            return
        self._expanded = True
        self.show()
        splitter = self._splitter
        if splitter is not None:
            total = max(sum(splitter.sizes()), splitter.width(), 1)
            sidebar_w = min(max(width, _MIN_WIDTH), max(_MIN_WIDTH, total // 2))
            splitter.setSizes([max(1, total - sidebar_w), sidebar_w])
        self._panel._refresh_quick_actions_from_context()
        self._panel.focus_input()

    def collapse(self) -> None:
        self._expanded = False
        splitter = self._splitter
        if splitter is not None:
            total = max(sum(splitter.sizes()), splitter.width(), 1)
            splitter.setSizes([total, 0])
        self.collapsed.emit()

    def show_and_ask(self, prompt: str, *, scene: str = "") -> bool:
        engine = self._engine
        panel = self._panel
        if engine is None or panel is None:
            return False
        resolved_scene = scene.strip() or "个股分析"
        engine.open_session_for_ask(
            surface="floating",
            session_policy="resume",
            scene=resolved_scene,
        )
        engine.switch_surface("floating")
        self.expand()
        panel.submit_prompt(prompt, auto_send=False)
        panel.focus_input()
        return True

    def deactivate(self) -> None:
        panel = self._panel
        if panel is not None:
            panel.deactivate(final=True)

    def _open_full_ai_page(self) -> None:
        main = self._find_main_window()
        if main is None:
            page_notify(self, "无法打开 AI 助手页", level="warning")
            return
        if hasattr(main, "_open_ai_page"):
            main._open_ai_page()
        if self._panel is not None:
            self._panel.focus_input()

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        from vnpy_ashare.ui.shell.main_window import AshareMainWindow

        parent: QtWidgets.QWidget | None = self
        while parent is not None:
            if isinstance(parent, AshareMainWindow):
                return parent
            parent = parent.parentWidget()
        return None

    def _on_theme_changed(self) -> None:
        panel = self._panel
        if panel is not None:
            bind_ai_panel_style(panel)
