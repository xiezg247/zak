"""由 ThemeTokens 生成 AI 模块 QSS。"""

from __future__ import annotations

from vnpy_common.ui.theme.tokens import DARK_TOKENS, ThemeTokens


def _build_chat_bubble_stylesheet(t: ThemeTokens) -> str:
    user_bg = t.table_selected if t.id == "light" else t.run_row_active_bg
    pending_bg = t.run_row_active_bg
    error_bg = t.danger_btn_bg
    return f"""
QLabel#AiBubbleUser {{
    background-color: {user_bg};
    color: {t.text_primary};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiBubbleAssistant,
QTextBrowser#AiBubbleAssistant {{
    background-color: {t.ai_assistant_bg};
    color: {t.text_primary};
    border: 1px solid {t.ai_assistant_border};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiBubblePending {{
    background-color: {pending_bg};
    color: {t.accent};
    border: 1px solid {t.accent_soft};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiBubbleError {{
    background-color: {error_bg};
    color: {t.danger_btn_text};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
"""


def _build_ai_message_scrollbar_stylesheet(t: ThemeTokens) -> str:
    """AI 对话消息区滚动条：加宽、提高对比度，避免与聊天背景融为一体。"""
    track = t.ai_assistant_border
    handle = t.combo_hover_border
    return f"""
QScrollArea#AiMessageScroll QScrollBar:vertical,
QScrollBar#AiMessageScrollBar:vertical {{
    background-color: {track};
    width: 12px;
    margin: 2px 1px 2px 0;
    border: none;
    border-radius: 6px;
}}
QScrollArea#AiMessageScroll QScrollBar::handle:vertical,
QScrollBar#AiMessageScrollBar::handle:vertical {{
    background-color: {handle};
    min-height: 48px;
    border-radius: 5px;
    margin: 2px;
    border: 1px solid {t.panel_border};
}}
QScrollArea#AiMessageScroll QScrollBar::handle:vertical:hover,
QScrollBar#AiMessageScrollBar::handle:vertical:hover {{
    background-color: {t.accent};
    border-color: {t.accent};
}}
QScrollArea#AiMessageScroll QScrollBar::handle:vertical:pressed,
QScrollBar#AiMessageScrollBar::handle:vertical:pressed {{
    background-color: {t.accent_hover};
    border-color: {t.accent_hover};
}}
QScrollArea#AiMessageScroll QScrollBar::add-line:vertical,
QScrollArea#AiMessageScroll QScrollBar::sub-line:vertical,
QScrollBar#AiMessageScrollBar::add-line:vertical,
QScrollBar#AiMessageScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollArea#AiMessageScroll QScrollBar::add-page:vertical,
QScrollArea#AiMessageScroll QScrollBar::sub-page:vertical,
QScrollBar#AiMessageScrollBar::add-page:vertical,
QScrollBar#AiMessageScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""


def _build_quick_action_stylesheet(t: ThemeTokens) -> str:
    chip_bg = t.panel_bg
    return f"""
QPushButton#AiQuickActionBtn {{
    background-color: {chip_bg};
    border: 1px solid {t.panel_border};
    border-radius: 12px;
    color: {t.text_secondary};
    font-size: 11px;
    padding: 5px 12px;
    min-height: 24px;
}}
QPushButton#AiQuickActionBtn:hover {{
    border-color: {t.accent};
    color: {t.accent};
}}
QToolButton#AiQuickActionBtn {{
    background-color: {chip_bg};
    border: 1px solid {t.panel_border};
    border-radius: 12px;
    color: {t.text_secondary};
    font-size: 11px;
    padding: 5px 12px;
    min-height: 24px;
}}
QToolButton#AiQuickActionBtn:hover {{
    border-color: {t.accent};
    color: {t.accent};
}}
QToolButton#AiQuickActionBtn::menu-indicator {{
    image: none;
    width: 0;
}}
QMenu#AiQuickActionMenu {{
    background-color: {chip_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    padding: 4px 0;
}}
QMenu#AiQuickActionMenu::item {{
    color: {t.text_primary};
    padding: 6px 16px;
    font-size: 12px;
}}
QMenu#AiQuickActionMenu::item:selected {{
    background-color: {t.menu_selected_bg};
    color: {t.menu_selected_text};
}}
QScrollArea#AiQuickActionScroll {{
    background-color: transparent;
    border: none;
}}
QWidget#AiQuickActionChips {{
    background-color: transparent;
}}
"""


def build_ai_panel_stylesheet(t: ThemeTokens) -> str:
    chat_bg = t.ai_chat_bg
    sidebar_bg = t.nav_bg
    context_bg = t.panel_bg
    return (
        f"""
QWidget#AiChatPanel {{
    background-color: {chat_bg};
    color: {t.text_primary};
}}
QScrollArea#AiMessageScroll {{
    background-color: {chat_bg};
    border: none;
}}
QWidget#AiMessageContainer {{
    background-color: {chat_bg};
}}
QLabel#AiContextLabel {{
    color: {t.text_secondary};
    font-size: 11px;
    padding: 4px 8px;
    background-color: {context_bg};
    border-radius: 4px;
}}
"""
        + _build_ai_message_scrollbar_stylesheet(t)
        + _build_chat_bubble_stylesheet(t)
        + f"""
QPlainTextEdit#AiInput {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 6px;
    padding: 8px;
    color: {t.input_text};
    font-size: 13px;
}}
QPlainTextEdit#AiInput:focus {{
    border-color: {t.accent};
}}
QPushButton#AiSendBtn {{
    background-color: {t.accent};
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: {t.action_btn_text};
    font-weight: bold;
}}
QPushButton#AiSendBtn:hover {{
    background-color: {t.accent_hover};
}}
QPushButton#AiSendBtn:disabled {{
    background-color: {t.input_disabled_bg};
    color: {t.input_disabled_text};
}}
QPushButton#AiToolBtn {{
    background-color: transparent;
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 4px 10px;
    color: {t.text_secondary};
    font-size: 12px;
}}
QPushButton#AiToolBtn:hover {{
    border-color: {t.accent};
    color: {t.accent};
}}
QPushButton#AiDeleteSessionsBtn {{
    background-color: transparent;
    border: 1px solid {t.danger_btn_border};
    border-radius: 4px;
    padding: 4px 10px;
    color: {t.danger_btn_text};
    font-size: 12px;
}}
"""
        + _build_quick_action_stylesheet(t)
        + f"""
QWidget#AiQuickActionChips {{
    margin-bottom: 4px;
}}
QLabel#AiTitle {{
    font-size: 14px;
    font-weight: bold;
    color: {t.text_primary};
}}
QLabel#AiConfigHint {{
    font-size: 11px;
    color: {t.text_muted};
}}
QWidget#AiSessionSidebar {{
    background-color: {sidebar_bg};
    border-right: 1px solid {t.panel_border};
}}
QSplitter#AiPageSplitter::handle {{
    background-color: {t.splitter_handle};
}}
QSplitter#AiPageSplitter::handle:hover {{
    background-color: {t.accent};
}}
QWidget#AiSessionRail {{
    background-color: {sidebar_bg};
    border-left: 1px solid {t.panel_border};
}}
QToolButton#AiSessionToggle {{
    background-color: transparent;
    border: 1px solid {t.input_border};
    border-radius: 4px;
    color: {t.text_secondary};
    font-size: 11px;
}}
QToolButton#AiSessionToggle:hover {{
    border-color: {t.accent};
    color: {t.accent};
}}
QWidget#AiSessionList {{
    background-color: transparent;
}}
QLabel#AiSessionTitle {{
    font-size: 13px;
    font-weight: bold;
    color: {t.run_row_title};
}}
QListWidget#AiSessionListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    color: {t.run_row_title};
    font-size: 12px;
}}
QListWidget#AiSessionListWidget::item {{
    padding: 0;
    border-radius: 6px;
    margin: 2px 0;
}}
QListWidget#AiSessionListWidget::item:selected,
QListWidget#AiSessionListWidget::item:hover {{
    background-color: transparent;
}}
QFrame#AiSessionRow {{
    background-color: transparent;
    border-radius: 6px;
    border-left: 3px solid transparent;
}}
QFrame#AiSessionRow[active="true"] {{
    background-color: {t.run_row_active_bg};
    border-left: 3px solid {t.accent};
}}
QFrame#AiSessionRow:hover {{
    background-color: {t.run_row_hover_bg};
}}
QLabel#AiSessionRowTitle {{
    color: {t.run_row_title};
    font-size: 12px;
    min-height: 16px;
}}
QLabel#AiSessionRowSubtitle {{
    color: {t.run_row_subtitle};
    font-size: 10px;
    min-height: 14px;
}}
QCheckBox#AiSessionCheck {{
    spacing: 0;
}}
QCheckBox#AiSessionCheck::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.checkbox_border};
    border-radius: 3px;
    background-color: {t.checkbox_bg};
}}
QCheckBox#AiSessionCheck::indicator:checked {{
    background-color: {t.accent};
    border-color: {t.accent};
}}
QCheckBox#AiSessionCheck::indicator:disabled {{
    background-color: {t.input_disabled_bg};
    border-color: {t.input_border};
}}
"""
    )


def build_ai_floating_stylesheet(t: ThemeTokens) -> str:
    chat_bg = t.ai_chat_bg
    title_bg = t.panel_bg
    chip_bg = t.panel_bg
    user_bg = t.table_selected if t.id == "light" else t.run_row_active_bg
    return (
        f"""
QWidget#FloatingAiPanel {{
    background-color: {chat_bg};
    border: 1px solid {t.panel_border};
    border-radius: 12px;
}}
QWidget#AiFloatingTitleBar {{
    background-color: {title_bg};
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid {t.panel_border};
}}
QLabel#AiFloatingGrip {{
    color: {t.text_hint};
    font-size: 12px;
    padding-right: 2px;
}}
QLabel#AiFloatingTitle {{
    color: {t.run_row_title};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QToolButton#AiFloatingIconBtn {{
    background-color: {t.btn_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    color: {t.text_secondary};
    font-size: 13px;
}}
QToolButton#AiFloatingIconBtn:hover {{
    background-color: {t.btn_hover_bg};
    border-color: {t.accent};
    color: {t.accent};
}}
QWidget#AiFloatingContextBar {{
    background-color: {chip_bg};
    border-bottom: 1px solid {t.panel_border};
}}
QLabel#AiFloatingContextChip {{
    color: {t.text_primary};
    font-size: 11px;
    padding: 6px 10px;
    background-color: {t.input_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QScrollArea#AiQuickActionScroll {{
    background-color: {chat_bg};
    border: none;
}}
"""
        + _build_quick_action_stylesheet(t)
        + f"""
QWidget#AiChatPanel {{
    background-color: {chat_bg};
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}}
QScrollArea#AiMessageScroll {{
    background-color: {chat_bg};
    border: none;
}}
QWidget#AiMessageContainer {{
    background-color: {chat_bg};
}}
QWidget#AiBubbleRow {{
    background-color: {chat_bg};
}}
"""
        + _build_ai_message_scrollbar_stylesheet(t)
        + f"""
QLabel#AiBubbleUser {{
    background-color: {user_bg};
    color: {t.text_primary};
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiBubbleAssistant,
QTextBrowser#AiBubbleAssistant {{
    background-color: {t.ai_assistant_bg};
    color: {t.text_primary};
    border: 1px solid {t.ai_assistant_border};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiBubblePending {{
    background-color: {t.run_row_active_bg};
    color: {t.accent};
    border: 1px solid {t.accent_soft};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiBubbleError {{
    background-color: {t.danger_btn_bg};
    color: {t.danger_btn_text};
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLabel#AiFloatingToolHint {{
    color: {t.accent};
    font-size: 11px;
    padding: 4px 8px;
    background-color: {chip_bg};
    border-radius: 4px;
}}
QPlainTextEdit#AiInput {{
    background-color: {t.input_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    padding: 6px 8px;
    color: {t.input_text};
    font-size: 13px;
    min-height: 44px;
}}
QPlainTextEdit#AiInput:focus {{
    border-color: {t.accent};
}}
QWidget#AiInputRow {{
    background-color: transparent;
}}
QWidget#AiQuickActionChips {{
    margin-bottom: 2px;
}}
QPushButton#AiSendBtn {{
    background-color: {t.accent};
    border: none;
    border-radius: 8px;
    color: {t.action_btn_text};
    font-size: 14px;
    font-weight: bold;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
}}
QPushButton#AiSendBtn:hover {{
    background-color: {t.accent_hover};
}}
QPushButton#AiSendBtn:disabled {{
    background-color: {t.input_disabled_bg};
    color: {t.input_disabled_text};
}}
QLabel#AiContextLabel {{
    color: {t.text_muted};
    font-size: 10px;
    padding: 2px 6px;
    background-color: {chip_bg};
    border-radius: 4px;
}}
"""
    )


def build_ai_tools_stylesheet(t: ThemeTokens) -> str:
    return f"""
QWidget#AiToolsStatusBar {{
    background-color: {t.panel_bg};
    border-radius: 4px;
    padding: 2px 4px;
}}
QLabel#AiToolsSummary {{
    color: {t.text_secondary};
    font-size: 11px;
    padding: 4px 6px;
}}
QLabel#AiToolsMeta {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QLabel#AiToolsSection {{
    color: {t.accent};
    font-size: 12px;
    font-weight: bold;
    margin-top: 4px;
}}
QLabel#AiToolsEmpty {{
    color: {t.text_muted};
    font-size: 12px;
    padding-left: 4px;
}}
QScrollArea#AiToolsScroll {{
    border: none;
    background-color: transparent;
}}
QFrame#AiToolsCard_ready {{
    background-color: {t.panel_bg};
    border: 1px solid {t.semantic_success};
    border-radius: 6px;
}}
QFrame#AiToolsCard_missing_env {{
    background-color: {t.panel_bg};
    border: 1px solid {t.semantic_warning};
    border-radius: 6px;
}}
QFrame#AiToolsCard_connect_failed {{
    background-color: {t.danger_btn_bg};
    border: 1px solid {t.danger_btn_border};
    border-radius: 6px;
}}
QFrame#AiToolsCard_disabled {{
    background-color: {t.input_disabled_bg};
    border: 1px solid {t.input_border};
    border-radius: 6px;
}}
QLabel#AiToolsCardTitle {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: bold;
}}
QLabel#AiToolsCardDetail {{
    color: {t.text_secondary};
    font-size: 11px;
}}
QLabel#AiToolsBadge_ready {{
    color: {t.semantic_success};
    font-size: 11px;
}}
QLabel#AiToolsBadge_missing_env {{
    color: {t.semantic_warning};
    font-size: 11px;
}}
QLabel#AiToolsBadge_connect_failed {{
    color: {t.danger_btn_text};
    font-size: 11px;
}}
QLabel#AiToolsBadge_disabled {{
    color: {t.text_muted};
    font-size: 11px;
}}
"""


def build_ai_trace_stylesheet(t: ThemeTokens) -> str:
    block_bg = t.screener_log_bg
    detail_bg = t.depth_bg
    return f"""
QFrame#AiInlineTraceBlock {{
    background-color: {block_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
}}
QLabel#AiInlineTraceHeader {{
    color: {t.text_secondary};
    font-size: 11px;
}}
QPushButton#AiInlineTraceStep {{
    color: {t.text_primary};
    font-size: 11px;
    text-align: left;
    padding: 2px 4px;
    border: none;
}}
QPushButton#AiInlineTraceStep:hover {{
    color: {t.text_primary};
    background-color: {t.table_hover};
    border-radius: 4px;
}}
QPushButton#AiInlineTraceStep[stepStatus="running"] {{
    color: {t.accent};
}}
QPushButton#AiInlineTraceStep[stepStatus="error"] {{
    color: {t.danger_btn_text};
}}
QPlainTextEdit#AiInlineTraceDetail {{
    background-color: {detail_bg};
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    color: {t.text_secondary};
    font-family: Menlo, Monaco, Consolas, monospace;
    font-size: 10px;
    padding: 6px;
}}
"""


PANEL_STYLESHEET = build_ai_panel_stylesheet(DARK_TOKENS)
FLOATING_CHAT_STYLESHEET = build_ai_floating_stylesheet(DARK_TOKENS)
TOOLS_WIDGET_STYLESHEET = build_ai_tools_stylesheet(DARK_TOKENS)
INLINE_TRACE_STYLESHEET = build_ai_trace_stylesheet(DARK_TOKENS)
