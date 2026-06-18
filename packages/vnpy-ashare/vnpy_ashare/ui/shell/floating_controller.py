"""悬浮球协调层：显隐、上下文、AskAi 路由。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context.store import get_ai_context
from vnpy_ashare.ai.ui.floating_actions import scene_label_from_context
from vnpy_ashare.app.events import AskAiRequest
from vnpy_common.ai.protocol import QuickAction
from vnpy_common.paths import QSETTINGS_ORG
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import clamp_point_in_parent, default_child_bottom_right_in_anchor
from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.ui.floating.panel import ORB_MARGIN, FloatingAiOrb, FloatingAiPanel
from vnpy_llm.ui.session.widgets import show_ai_session_dialog

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.main_window import AshareMainWindow

FLOATING_ORB_PAGE_KEYS = frozenset({"watchlist", "market", "sector_flow", "radar", "local", "screener"})
SCREENER_ATTENTION_SOURCES = frozenset({"screener", "auto_screener"})
ORB_POSITION_KEY = "orb_position_content"


class FloatingAiController(QtCore.QObject):
    """管理悬浮球与精简面板的显隐、上下文同步与快捷动作。"""

    def __init__(self, host: AshareMainWindow, llm_engine: LlmEngine) -> None:
        super().__init__(host)
        self._host = host
        self._engine = llm_engine
        self._orb: FloatingAiOrb | None = None
        self._panel: FloatingAiPanel | None = None
        self._content_anchor: QtWidgets.QWidget | None = None
        self._orb_user_hidden = self._load_orb_user_hidden()
        self._overlay_parents: list[QtWidgets.QWidget] = []
        self._current_page_key: Callable[[], str | None] = lambda: None

    @property
    def orb(self) -> FloatingAiOrb | None:
        return self._orb

    @property
    def panel(self) -> FloatingAiPanel | None:
        return self._panel

    def bind_page_key(self, provider: Callable[[], str | None]) -> None:
        self._current_page_key = provider

    def bind_content_anchor(self, anchor: QtWidgets.QWidget) -> None:
        self._content_anchor = anchor

    def init(self, shell: QtWidgets.QWidget) -> bool:
        if self._orb is not None:
            return True

        orb = FloatingAiOrb(shell, position_key=ORB_POSITION_KEY)
        orb.clicked.connect(self._on_orb_open_chat)
        orb.fullscreen_requested.connect(self._host._open_ai_page)
        orb.history_requested.connect(self._open_history)
        orb.new_session_requested.connect(self._on_new_session)
        orb.tools_requested.connect(self._host._open_ai_tools_dialog)
        orb.hide_requested.connect(lambda: self.hide_orb(user_initiated=True))
        orb.quick_action_requested.connect(lambda prompt: self.run_quick_action(prompt=prompt, auto_send=False))
        self._orb = orb

        panel = FloatingAiPanel(self._engine, parent=shell)
        panel.expand_requested.connect(self._host._open_ai_page)
        panel.panel_minimized.connect(self.hide_panel)
        panel.new_session_requested.connect(self._on_new_session)
        panel.history_requested.connect(self._open_history)
        panel.quick_action_triggered.connect(self._on_panel_quick_action)
        self._panel = panel

        self._engine.signals.context_changed.connect(self.refresh_context)
        QtCore.QTimer.singleShot(0, self._restore_orb_position)
        orb.hide()
        panel.hide()
        self.refresh_context()
        return True

    @staticmethod
    def is_page_allowed(page_key: str) -> bool:
        return page_key in FLOATING_ORB_PAGE_KEYS

    def prefers_floating_for_ask(self) -> bool:
        """当前页是否应以悬浮面板承接 AskAi（白名单页且用户未隐藏悬浮球）。"""
        page_key = self._current_page_key()
        if not page_key or not self.is_page_allowed(page_key):
            return False
        return not self._orb_user_hidden

    def on_page_changed(self, page_key: str) -> None:
        if self._orb is None:
            return
        if self.is_page_allowed(page_key):
            self.hide_panel()
            if not self._orb_user_hidden:
                self.show_orb()
        else:
            self.hide_panel()
            self._orb.hide()

    def on_window_resize(self) -> None:
        shell = self._shell_widget()
        if shell is None:
            return
        panel = self._panel
        if panel is not None and panel.isVisible():
            panel.clamp_geometry_to_parent()
        orb = self._orb
        if orb is None or not orb.isVisible():
            return
        self._restore_orb_position()
        orb.move(clamp_point_in_parent(shell, orb, orb.pos()))

    def raise_floating_layers(self) -> None:
        orb = self._orb
        panel = self._panel
        if orb is not None and orb.isVisible():
            orb.raise_()
        if panel is not None and panel.isVisible():
            panel.raise_()

    def toggle_orb(self) -> None:
        page_key = self._current_page_key()
        if page_key == "ai_assistant":
            self.return_from_fullscreen()
            return
        if page_key and not self.is_page_allowed(page_key):
            page_notify(
                self._host,
                "AI 悬浮球仅在自选、市场、板块资金、雷达、本地、选股页可用。",
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

    def push_overlay_parent(self, parent: QtWidgets.QWidget) -> None:
        """模态 overlay 打开时隐藏主窗口悬浮球，后续 AskAi 可挂到 overlay 父控件。"""
        if parent in self._overlay_parents:
            return
        self._overlay_parents.append(parent)
        self.hide_orb(user_initiated=False)

    def pop_overlay_parent(self, parent: QtWidgets.QWidget) -> None:
        """overlay 关闭时收回面板并恢复悬浮球显隐逻辑。"""
        try:
            self._overlay_parents.remove(parent)
        except ValueError:
            return
        panel = self._panel
        if panel is not None and panel.parentWidget() is parent:
            panel.hide()
            shell = self._shell_widget()
            if shell is not None:
                panel.setParent(shell)
        if not self._overlay_parents:
            page_key = self._current_page_key()
            if page_key and self.is_page_allowed(page_key) and not self._orb_user_hidden:
                self.show_orb()

    def on_overlay_parent_resized(self, parent: QtWidgets.QWidget) -> None:
        panel = self._panel
        if panel is not None and panel.isVisible() and panel.parentWidget() is parent:
            panel.clamp_geometry_to_parent()

    def handle_ask_ai(self, data: AskAiRequest) -> None:
        parent = data.panel_parent
        if isinstance(parent, QtWidgets.QWidget):
            self._show_panel_on_parent(parent, data)
            return
        if not self._orb or not self.prefers_floating_for_ask():
            return
        self.show_orb()
        self.show_panel(
            new_session=data.new_session,
            session_policy=data.session_policy,
            scene=data.scene or data.source_page,
        )
        if self._panel is not None:
            self._panel.submit_prompt(
                data.prompt,
                auto_send=False,
                action_id=data.action_id,
            )

    def _show_panel_on_parent(self, parent: QtWidgets.QWidget, data: AskAiRequest) -> None:
        panel = self._panel
        if panel is None:
            return
        self.hide_orb(user_initiated=False)
        resolved_scene = (data.scene or data.source_page or "").strip() or self._scene_from_context()
        self._prepare_floating_session(
            new_session=data.new_session,
            session_policy=data.session_policy,
            scene=resolved_scene,
        )
        panel.setParent(parent)
        panel.show_aligned_in_parent(parent)
        panel.raise_()
        panel.focus_input()
        panel.submit_prompt(
            data.prompt,
            auto_send=False,
            action_id=data.action_id,
        )

    def run_quick_action(
        self,
        *,
        prompt: str,
        auto_send: bool = False,
        action_id: str = "",
    ) -> None:
        del auto_send  # 快捷操作统一预填，由用户手动发送
        if not prompt.strip():
            return
        self.show_panel(scene=self._scene_from_context())
        if self._panel is not None:
            self._panel.submit_prompt(prompt, auto_send=False, action_id=action_id)

    def refresh_context(self, _text: str = "") -> None:
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
        if source in SCREENER_ATTENTION_SOURCES:
            if page_key != "screener":
                return
        elif source and page_key != source:
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
        self._restore_orb_position()
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
        shell = self._shell_widget()
        if shell is not None and panel.parentWidget() is not shell:
            panel.setParent(shell)
        if not orb.isVisible():
            self.show_orb()
        panel.show_near_orb(orb)
        panel.raise_()
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
            if parent is not None and isinstance(parent, QtWidgets.QWidget):
                return parent
        widget = self._host.centralWidget()
        return widget if isinstance(widget, QtWidgets.QWidget) else None

    def _default_orb_position(self) -> tuple[int, int]:
        host = self._shell_widget()
        orb = self._orb
        anchor = self._content_anchor
        if host is None or orb is None:
            return 0, 0
        if anchor is not None and anchor.width() > 0 and anchor.height() > 0:
            point = default_child_bottom_right_in_anchor(
                host,
                orb,
                anchor,
                margin=ORB_MARGIN,
            )
            return point.x(), point.y()
        return (
            max(0, host.width() - orb.width() - ORB_MARGIN),
            max(0, host.height() - orb.height() - ORB_MARGIN),
        )

    def _restore_orb_position(self) -> None:
        orb = self._orb
        host = self._shell_widget()
        if orb is None or host is None:
            return
        default_x, default_y = self._default_orb_position()
        orb.restore_position(host, default_x=default_x, default_y=default_y)

    def _on_orb_open_chat(self) -> None:
        if self.panel_visible():
            self.hide_panel()
        else:
            self.show_panel()

    def _on_panel_quick_action(self, action: object) -> None:
        if not isinstance(action, QuickAction):
            return
        self.run_quick_action(
            prompt=action.prompt,
            auto_send=False,
            action_id=action.id,
        )

    @staticmethod
    def _scene_from_context() -> str:
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
            page_notify(self._host, "请等待当前回复完成后再新建会话")
            return
        self._engine.new_session(surface="floating")
        self.show_panel()

    def _open_history(self) -> None:
        self._engine.switch_surface("floating")
        self.show_orb()
        show_ai_session_dialog(self._engine, self._host)

    @staticmethod
    def _load_orb_user_hidden() -> bool:
        settings = QtCore.QSettings(QSETTINGS_ORG, "floating_ai")
        value = settings.value("orb_user_hidden", False)
        return value is True or value == "true"

    def _save_orb_user_hidden(self) -> None:
        settings = QtCore.QSettings(QSETTINGS_ORG, "floating_ai")
        settings.setValue("orb_user_hidden", self._orb_user_hidden)
