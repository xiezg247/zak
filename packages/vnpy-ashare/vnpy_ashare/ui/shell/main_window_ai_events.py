"""主窗口 AI Event 分发与 LLM 入口。"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.app.events import (
    AiActionRequest,
    AskAiRequest,
    BacktestRequest,
    BatchBacktestViewRequest,
    FillRecipeRequest,
    FillScreenerRequest,
    OrbAttentionRequest,
)
from vnpy_ashare.domain.ai.actions import (
    AI_ACTION_ASK_AI,
    AI_ACTION_FILL_RECIPE,
    AI_ACTION_FILL_SCREENER,
    AI_ACTION_OPEN_BACKTEST,
    AI_ACTION_OPEN_BATCH_BACKTEST,
    AI_ACTION_ORB_ATTENTION,
    normalize_ai_action,
)
from vnpy_ashare.ui.shell.main_window_pages import open_backtest_dialog, open_batch_backtest_dialog
from vnpy_common.ui.feedback import page_notify

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.ui.shell.main_window import AshareMainWindow
    from vnpy_llm.app.engine import LlmEngine

AI_NOT_LOADED_MSG = "AI 助手未加载，请确认已安装并启用 vnpy_llm"


def import_llm_module(module_path: str) -> ModuleType | None:
    try:
        return import_module(module_path)
    except ImportError:
        return None


def get_llm_engine(main_engine: MainEngine) -> LlmEngine | None:
    llm_mod = import_llm_module("vnpy_llm.app.engine")
    if llm_mod is None:
        return None
    engine = main_engine.get_engine(llm_mod.APP_NAME)
    if isinstance(engine, llm_mod.LlmEngine):
        return engine
    return None


def open_ai_page(win: AshareMainWindow) -> None:
    llm_engine = get_llm_engine(win.main_engine)
    if llm_engine is None:
        page_notify(win, AI_NOT_LOADED_MSG, level="warning")
        return
    llm_engine.open_session_for_ask(surface="assistant")
    index = win._nav_index_for_key("ai_assistant")
    if index is None:
        return
    win._show_page(index)


def on_open_backtest_event(win: AshareMainWindow, event: Event) -> None:
    if isinstance(event.data, BacktestRequest):
        win._signal_open_backtest.emit(event.data)


def handle_open_backtest(win: AshareMainWindow, data: BacktestRequest) -> None:
    open_backtest_dialog(win, data)


def on_open_batch_backtest_event(win: AshareMainWindow, event: Event) -> None:
    if isinstance(event.data, BatchBacktestViewRequest):
        win._signal_open_batch_backtest.emit(event.data)


def handle_open_batch_backtest(win: AshareMainWindow, data: BatchBacktestViewRequest) -> None:
    open_batch_backtest_dialog(win, data)


def on_fill_screener_event(win: AshareMainWindow, event: Event) -> None:
    if isinstance(event.data, FillScreenerRequest):
        win._signal_fill_screener.emit(event.data)


def handle_fill_screener(win: AshareMainWindow, data: FillScreenerRequest) -> None:
    index = win._nav_index_for_key("screener")
    if index is None:
        return
    win._show_page(index)
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "apply_request"):
        widget.apply_request(data)


def handle_fill_recipe(win: AshareMainWindow, data: FillRecipeRequest) -> None:
    index = win._nav_index_for_key("screener")
    if index is None:
        return
    win._show_page(index)
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "apply_recipe_request"):
        widget.apply_recipe_request(data)


def on_ask_ai_event(win: AshareMainWindow, event: Event) -> None:
    if isinstance(event.data, AskAiRequest):
        win._signal_ask_ai.emit(event.data)


def on_orb_attention_event(win: AshareMainWindow, event: Event) -> None:
    if isinstance(event.data, OrbAttentionRequest):
        win._signal_orb_attention.emit(event.data)


def on_ai_action_event(win: AshareMainWindow, event: Event) -> None:
    if isinstance(event.data, AiActionRequest):
        win._signal_ai_action.emit(event.data)


def handle_ai_action(win: AshareMainWindow, data: AiActionRequest) -> None:
    try:
        action = normalize_ai_action(data)
    except (TypeError, ValueError):
        return
    payload = action.payload
    if action.kind == AI_ACTION_FILL_SCREENER:
        assert isinstance(payload, FillScreenerRequest)
        handle_fill_screener(win, payload)
    elif action.kind == AI_ACTION_FILL_RECIPE:
        assert isinstance(payload, FillRecipeRequest)
        handle_fill_recipe(win, payload)
    elif action.kind == AI_ACTION_ASK_AI:
        assert isinstance(payload, AskAiRequest)
        handle_ask_ai(win, payload)
    elif action.kind == AI_ACTION_OPEN_BACKTEST:
        assert isinstance(payload, BacktestRequest)
        handle_open_backtest(win, payload)
    elif action.kind == AI_ACTION_OPEN_BATCH_BACKTEST:
        assert isinstance(payload, BatchBacktestViewRequest)
        handle_open_batch_backtest(win, payload)
    elif action.kind == AI_ACTION_ORB_ATTENTION:
        assert isinstance(payload, OrbAttentionRequest)
        handle_orb_attention(win, payload)


def handle_orb_attention(win: AshareMainWindow, data: OrbAttentionRequest) -> None:
    if not win._ensure_floating_ai():
        return
    if win._floating_controller is not None:
        win._floating_controller.notify_attention(data.source)


def should_use_floating_ai(win: AshareMainWindow, data: AskAiRequest) -> bool:
    if data.use_full_page:
        return False
    if not win._ensure_floating_ai():
        return False
    controller = win._floating_controller
    return controller is not None and controller.prefers_floating_for_ask()


def handle_ask_ai(win: AshareMainWindow, data: AskAiRequest) -> None:
    if isinstance(data.panel_parent, QtWidgets.QWidget):
        if win._ensure_floating_ai() and win._floating_controller is not None:
            win._floating_controller.handle_ask_ai(data)
        else:
            open_ai_assistant_with_request(win, data)
        return
    if should_use_floating_ai(win, data):
        assert win._floating_controller is not None
        win._floating_controller.handle_ask_ai(data)
        return
    open_ai_assistant_with_request(win, data)


def open_ai_assistant_with_request(win: AshareMainWindow, data: AskAiRequest) -> None:
    llm_engine = get_llm_engine(win.main_engine)
    if llm_engine is None:
        page_notify(win, AI_NOT_LOADED_MSG, level="warning")
        return
    llm_engine.open_session_for_ask(
        surface="assistant",
        new_session=data.new_session,
        session_policy=data.session_policy,
        scene=data.scene or data.source_page,
    )
    index = win._nav_index_for_key("ai_assistant")
    if index is None:
        return
    win._show_page(index)
    widget = win._page_widgets.get("ai_assistant")
    if widget is not None and hasattr(widget, "submit_prompt"):
        widget.submit_prompt(
            data.prompt,
            auto_send=False,
            action_id=data.action_id,
        )
    elif widget is not None and hasattr(widget, "set_input_text"):
        widget.set_input_text(data.prompt)


def open_ai_tools_dialog(win: AshareMainWindow) -> None:
    llm_engine = get_llm_engine(win.main_engine)
    if llm_engine is None:
        page_notify(win, AI_NOT_LOADED_MSG, level="warning")
        return
    tools_mod = import_llm_module("vnpy_llm.ui.dialogs.tools")
    if tools_mod is None:
        page_notify(win, AI_NOT_LOADED_MSG, level="warning")
        return
    tools_mod.show_ai_tools_dialog(llm_engine, win)


def open_ai_tool_audit_dialog(win: AshareMainWindow) -> None:
    llm_engine = get_llm_engine(win.main_engine)
    if llm_engine is None:
        page_notify(win, AI_NOT_LOADED_MSG, level="warning")
        return
    audit_mod = import_llm_module("vnpy_llm.ui.dialogs.tool_audit")
    if audit_mod is None:
        page_notify(win, AI_NOT_LOADED_MSG, level="warning")
        return
    audit_mod.show_ai_tool_audit_dialog(llm_engine, win)
