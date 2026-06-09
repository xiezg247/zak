"""悬浮球协调层：显隐、上下文、AskAi 路由。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.events import AskAiRequest
from vnpy_llm.engine import LlmEngine
from vnpy_llm.ui.floating_panel import FloatingAiOrb, FloatingAiPanel

if TYPE_CHECKING:
    from vnpy_ashare.ui.main_window import AshareMainWindow

FLOATING_ORB_PAGE_KEYS = frozenset({"watchlist", "market", "local", "screener"})


class FloatingAiController(QtCore.QObject):
    """管理悬浮球与精简面板的显隐、上下文同步与快捷动作。"""

    def __init__(self, host: AshareMainWindow, llm_engine: LlmEngine) -> None:
        super().__init__(host)
        self._host = host
        self._engine = llm_engine
        self._orb: FloatingAiOrb | None = None
        self._panel: FloatingAiPanel | None = None
        self._orb_user_hidden = self._load_orb_user_hidden()
        self._current_page_key: Callable[[], str | None] = lambda: None

    @property
    def orb(self) -> FloatingAiOrb | None:
        return self._orb

    @property
    def panel(self) -> FloatingAiPanel | None:
        return self._panel

    def bind_page_key(self, provider: Callable[[], str | None]) -> None:
        self._current_page_key = provider

    def init(self, shell: QtWidgets.QWidget) -> bool:
        if self._orb is not None:
            return True

        orb = FloatingAiOrb(shell)
        orb.clicked.connect(self._on_orb_open_chat)
        orb.fullscreen_requested.connect(self._host._open_ai_page)
        orb.history_requested.connect(self._open_history)
        orb.new_session_requested.connect(self._on_new_session)
        orb.tools_requested.connect(self._host._open_ai_tools_dialog)
        orb.hide_requested.connect(lambda: self.hide_orb(user_initiated=True))
        orb.quick_action_requested.connect(
            lambda prompt: self.run_quick_action(prompt=prompt, auto_send=False)
        )
        self._orb = orb

        panel = FloatingAiPanel(self._engine, parent=shell)
        panel.expand_requested.connect(self._host._open_ai_page)
        panel.panel_minimized.connect(self.hide_panel)
        panel.new_session_requested.connect(self._on_new_session)
        panel.history_requested.connect(self._open_history)
        panel.quick_action_triggered.connect(self._on_panel_quick_action)
        self._panel = panel

        self._engine.signals.context_changed.connect(self.refresh_context)
        orb.restore_position(shell)
        orb.hide()
        self.refresh_context()
        return True

    @staticmethod
    def is_page_allowed(page_key: str) -> bool:
        return page_key in FLOATING_ORB_PAGE_KEYS

    def on_page_changed(self, page_key: str) -> None:
        if self._orb is None:
            return
        if self.is_page_allowed(page_key):
            if not self._orb_user_hidden:
                self.show_orb()
        else:
            self.hide_panel()
            self._orb.hide()

    def on_window_resize(self) -> None:
        orb = self._orb
        if orb is None or not orb.isVisible():
            return
        shell = self._shell_widget()
        if shell is not None:
            orb.clamp_to_parent(shell)

    def toggle_orb(self) -> None:
        page_key = self._current_page_key()
        if page_key == "ai_assistant":
            self.return_from_fullscreen()
            return
        if page_key and not self.is_page_allowed(page_key):
            QtWidgets.QMessageBox.information(
                self._host,
                "提示",
                "AI 悬浮球仅在自选、市场、本地、选股页可用。",
            )
            return
        if self.orb_visible():
            self.hide_orb(user_initiated=True)
        else:
            self.show_orb()

    def return_from_fullscreen(self) -> None:
        self._orb_user_hidden = False
        self._save_orb_user_hidden()
        self._host._show_page(self._host._page_before_ai)
        self.show_panel()

    def handle_ask_ai(self, data: AskAiRequest) -> None:
        if not self._orb:
            return
        page_key = self._current_page_key()
        if page_key and not self.is_page_allowed(page_key):
            index = self._host._nav_index_for_key("watchlist")
            if index is not None:
                self._orb_user_hidden = False
                self._host._show_page(index)
        self._orb_user_hidden = False
        self.show_orb()
        self.show_panel(
            new_session=data.new_session,
            session_policy=data.session_policy,
            scene=data.scene or data.source_page,
        )
        if self._panel is not None:
            self._panel.submit_prompt(
                data.prompt,
                auto_send=data.auto_send,
                action_id=data.action_id,
            )

    def run_quick_action(
        self,
        *,
        prompt: str,
        auto_send: bool,
        action_id: str = "",
    ) -> None:
        if not prompt.strip():
            return
        self.show_panel(scene=self._scene_from_context())
        if self._panel is not None:
            self._panel.submit_prompt(prompt, auto_send=auto_send, action_id=action_id)

    def refresh_context(self, _text: str = "") -> None:
        from vnpy_ashare.ai.context_store import get_ai_context

        data = get_ai_context()
        if self._orb is not None:
            self._orb.apply_context(data)
        if self._panel is not None:
            self._panel.apply_context(data)

    def orb_visible(self) -> bool:
        return self._orb is not None and self._orb.isVisible()

    def panel_visible(self) -> bool:
        return self._panel is not None and self._panel.isVisible()

    def hide_panel(self) -> None:
        if self._panel is not None:
            self._panel.hide()

    def hide_orb(self, *, user_initiated: bool = True) -> None:
        self.hide_panel()
        if self._orb is not None:
            self._orb.hide()
        if user_initiated:
            self._orb_user_hidden = True
            self._save_orb_user_hidden()

    def notify_attention(self, source: str = "") -> None:
        """刷新上下文并播放悬浮球提示动画（不展开面板）。"""
        self.refresh_context()
        if self._orb is None or self._orb_user_hidden:
            return
        page_key = self._current_page_key()
        if source == "screener" and page_key != "screener":
            return
        if not page_key or not self.is_page_allowed(page_key):
            return
        if not self.orb_visible():
            self.show_orb()
        self._orb.play_attention_pulse()

    def show_orb(self) -> None:
        orb = self._orb
        if orb is None:
            return
        page_key = self._current_page_key()
        if page_key and not self.is_page_allowed(page_key):
            return
        shell = self._shell_widget()
        if shell is not None:
            orb.restore_position(shell)
        orb.show()
        orb.raise_()
        self._orb_user_hidden = False
        self._save_orb_user_hidden()

    def show_panel(
        self,
        *,
        new_session: bool = False,
        session_policy: str = "resume",
        scene: str = "",
    ) -> None:
        orb = self._orb
        panel = self._panel
        if orb is None or panel is None:
            return
        resolved_scene = scene.strip() or self._scene_from_context()
        self._prepare_floating_session(
            new_session=new_session,
            session_policy=session_policy,
            scene=resolved_scene,
        )
        if not orb.isVisible():
            self.show_orb()
        panel.show_near_orb(orb)
        panel.focus_input()

    def on_ai_assistant_entered(self) -> None:
        self.hide_panel()
        if self._orb is not None:
            self._orb.hide()

    def deactivate(self) -> None:
        if self._panel is not None:
            self._panel.deactivate()
        if self._orb is not None:
            self._orb.hide()

    def _shell_widget(self) -> QtWidgets.QWidget | None:
        orb = self._orb
        if orb is not None:
            parent = orb.parentWidget()
            if parent is not None:
                return parent
        widget = self._host.centralWidget()
        return widget if isinstance(widget, QtWidgets.QWidget) else None

    def _on_orb_open_chat(self) -> None:
        if self.panel_visible():
            self.hide_panel()
        else:
            self.show_panel()

    def _on_panel_quick_action(self, action: object) -> None:
        from vnpy_ashare.ai.context import QuickAction

        if not isinstance(action, QuickAction):
            return
        self.run_quick_action(
            prompt=action.prompt,
            auto_send=action.auto_send,
            action_id=action.id,
        )

    @staticmethod
    def _scene_from_context() -> str:
        from vnpy_ashare.ai.context_store import get_ai_context
        from vnpy_llm.ui.floating_actions import scene_label_from_context

        return scene_label_from_context(get_ai_context())

    def _prepare_floating_session(
        self,
        *,
        new_session: bool = False,
        session_policy: str = "resume",
        scene: str = "",
    ) -> None:
        self._engine.open_session_for_ask(
            surface="floating",
            new_session=new_session,
            session_policy=session_policy,
            scene=scene,
        )

    def _on_new_session(self) -> None:
        if self._engine.is_busy():
            QtWidgets.QMessageBox.information(self._host, "提示", "请等待当前回复完成后再新建会话")
            return
        self._engine.new_session(surface="floating")
        self.show_panel()

    def _open_history(self) -> None:
        from vnpy_llm.ui.session_widgets import show_ai_session_dialog

        self._engine.switch_surface("floating")
        self.show_orb()
        show_ai_session_dialog(self._engine, self._host)

    @staticmethod
    def _load_orb_user_hidden() -> bool:
        settings = QtCore.QSettings("vnpy_zak", "floating_ai")
        value = settings.value("orb_user_hidden", False)
        return value is True or value == "true"

    def _save_orb_user_hidden(self) -> None:
        settings = QtCore.QSettings("vnpy_zak", "floating_ai")
        settings.setValue("orb_user_hidden", self._orb_user_hidden)
