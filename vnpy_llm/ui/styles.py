"""AI 面板样式。"""

_AI_QUICK_ACTION_STYLESHEET = """
QPushButton#AiQuickActionBtn {
    background-color: #1e1e26;
    border: 1px solid #2e2e38;
    border-radius: 12px;
    color: #a8b0c0;
    font-size: 11px;
    padding: 5px 12px;
    min-height: 24px;
}
QPushButton#AiQuickActionBtn:hover {
    border-color: #4a9eff;
    color: #4a9eff;
}
QToolButton#AiQuickActionBtn {
    background-color: #1e1e26;
    border: 1px solid #2e2e38;
    border-radius: 12px;
    color: #a8b0c0;
    font-size: 11px;
    padding: 5px 12px;
    min-height: 24px;
}
QToolButton#AiQuickActionBtn:hover {
    border-color: #4a9eff;
    color: #4a9eff;
}
QToolButton#AiQuickActionBtn::menu-indicator {
    image: none;
    width: 0;
}
QMenu#AiQuickActionMenu {
    background-color: #1e1e26;
    border: 1px solid #2e2e38;
    border-radius: 8px;
    padding: 4px 0;
}
QMenu#AiQuickActionMenu::item {
    color: #c8c8d0;
    padding: 6px 16px;
    font-size: 12px;
}
QMenu#AiQuickActionMenu::item:selected {
    background-color: #2a3a55;
    color: #ffffff;
}
QScrollArea#AiQuickActionScroll {
    background-color: transparent;
    border: none;
}
QWidget#AiQuickActionChips {
    background-color: transparent;
}
"""

_AI_CHAT_BUBBLE_STYLESHEET = """
QLabel#AiBubbleUser {
    background-color: #2a3a55;
    color: #e8e8e8;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiBubbleAssistant,
QTextBrowser#AiBubbleAssistant {
    background-color: #1e1e24;
    color: #e0e0e0;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiBubblePending {
    background-color: #1a2230;
    color: #4a9eff;
    border: 1px solid #2a4060;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiBubbleError {
    background-color: #3a2020;
    color: #ff8a8a;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
"""

PANEL_STYLESHEET = (
    """
QWidget#AiChatPanel {
    background-color: #141418;
    color: #e0e0e0;
}
QScrollArea#AiMessageScroll {
    background-color: #141418;
    border: none;
}
QWidget#AiMessageContainer {
    background-color: #141418;
}
QLabel#AiContextLabel {
    color: #8a8a95;
    font-size: 11px;
    padding: 4px 8px;
    background-color: #1a1a22;
    border-radius: 4px;
}
"""
    + _AI_CHAT_BUBBLE_STYLESHEET
    + """
QPlainTextEdit#AiInput {
    background-color: #1e1e24;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px;
    color: #e0e0e0;
    font-size: 13px;
}
QPlainTextEdit#AiInput:focus {
    border-color: #4a9eff;
}
QPushButton#AiSendBtn {
    background-color: #4a9eff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #fff;
    font-weight: bold;
}
QPushButton#AiSendBtn:hover {
    background-color: #5aadff;
}
QPushButton#AiSendBtn:disabled {
    background-color: #2a2a30;
    color: #666;
}
QPushButton#AiToolBtn {
    background-color: transparent;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 4px 10px;
    color: #a0a0a8;
    font-size: 12px;
}
QPushButton#AiToolBtn:hover {
    border-color: #4a9eff;
    color: #4a9eff;
}
QPushButton#AiDeleteSessionsBtn {
    background-color: transparent;
    border: 1px solid #d04a4a;
    border-radius: 4px;
    padding: 4px 10px;
    color: #d04a4a;
    font-size: 12px;
}
"""
    + _AI_QUICK_ACTION_STYLESHEET
    + """
QWidget#AiQuickActionChips {
    margin-bottom: 4px;
}
QLabel#AiTitle {
    font-size: 14px;
    font-weight: bold;
    color: #e0e0e0;
}
QLabel#AiConfigHint {
    font-size: 11px;
    color: #6a6a72;
}
QWidget#AiSessionSidebar {
    background-color: #101014;
    border-right: 1px solid #2a2a30;
}
QWidget#AiSessionRail {
    background-color: #101014;
    border-left: 1px solid #2a2a30;
}
QToolButton#AiSessionToggle {
    background-color: transparent;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    color: #a0a0a8;
    font-size: 11px;
}
QToolButton#AiSessionToggle:hover {
    border-color: #4a9eff;
    color: #4a9eff;
}
QWidget#AiSessionList {
    background-color: transparent;
}
QLabel#AiSessionTitle {
    font-size: 13px;
    font-weight: bold;
    color: #c0c0c8;
}
QListWidget#AiSessionListWidget {
    background-color: transparent;
    border: none;
    outline: none;
    color: #d0d0d8;
    font-size: 12px;
}
QListWidget#AiSessionListWidget::item {
    padding: 8px 10px;
    border-radius: 6px;
    margin: 2px 0;
}
QListWidget#AiSessionListWidget::item:selected {
    background-color: #2a3a55;
    color: #ffffff;
}
QListWidget#AiSessionListWidget::item:hover {
    background-color: #1e1e28;
}
"""
)

FLOATING_CHAT_STYLESHEET = (
    """
QWidget#FloatingAiPanel {
    background-color: #141418;
    border: 1px solid #2e2e38;
    border-radius: 12px;
}
QWidget#AiFloatingTitleBar {
    background-color: #1a1a22;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #2a2a34;
}
QLabel#AiFloatingGrip {
    color: #5a5a66;
    font-size: 12px;
    padding-right: 2px;
}
QLabel#AiFloatingTitle {
    color: #c8c8d0;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QToolButton#AiFloatingIconBtn {
    background-color: #252530;
    border: 1px solid #333340;
    border-radius: 4px;
    color: #9090a0;
    font-size: 13px;
}
QToolButton#AiFloatingIconBtn:hover {
    background-color: #2e2e3a;
    border-color: #4a9eff;
    color: #4a9eff;
}
QWidget#AiFloatingContextBar {
    background-color: #181820;
    border-bottom: 1px solid #2a2a34;
}
QLabel#AiFloatingContextChip {
    color: #b8c0d0;
    font-size: 11px;
    padding: 6px 10px;
    background-color: #1e1e28;
    border: 1px solid #2e2e38;
    border-radius: 6px;
}
QScrollArea#AiQuickActionScroll {
    background-color: #141418;
    border: none;
}
"""
    + _AI_QUICK_ACTION_STYLESHEET
)

FLOATING_CHAT_INNER_STYLESHEET = """
QWidget#AiChatPanel {
    background-color: #141418;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}
QScrollArea#AiMessageScroll {
    background-color: #141418;
    border: none;
}
QWidget#AiMessageContainer {
    background-color: #141418;
}
QWidget#AiBubbleRow {
    background-color: #141418;
}
QLabel#AiBubbleUser {
    background-color: #2a4060;
    color: #eef0f4;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiBubbleAssistant,
QTextBrowser#AiBubbleAssistant {
    background-color: #1e1e26;
    color: #e8e8f0;
    border: 1px solid #2a2a34;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiBubblePending {
    background-color: #1a2230;
    color: #4a9eff;
    border: 1px solid #2a4060;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiBubbleError {
    background-color: #3a2020;
    color: #ff8a8a;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
}
QLabel#AiFloatingToolHint {
    color: #4a9eff;
    font-size: 11px;
    padding: 4px 8px;
    background-color: #1a1a22;
    border-radius: 4px;
}
QPlainTextEdit#AiInput {
    background-color: #1a1a22;
    border: 1px solid #2e2e38;
    border-radius: 8px;
    padding: 6px 8px;
    color: #e0e0e8;
    font-size: 13px;
    min-height: 44px;
}
QPlainTextEdit#AiInput:focus {
    border-color: #4a9eff;
}
QWidget#AiInputRow {
    background-color: transparent;
}
QWidget#AiQuickActionChips {
    margin-bottom: 2px;
}
QPushButton#AiSendBtn {
    background-color: #4a9eff;
    border: none;
    border-radius: 8px;
    color: #fff;
    font-size: 14px;
    font-weight: bold;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
}
QPushButton#AiSendBtn:hover {
    background-color: #5aadff;
}
QPushButton#AiSendBtn:disabled {
    background-color: #2a2a32;
    color: #555;
}
QLabel#AiContextLabel {
    color: #7a7a88;
    font-size: 10px;
    padding: 2px 6px;
    background-color: #1e1e26;
    border-radius: 4px;
}
"""

TOOLS_WIDGET_STYLESHEET = """
QWidget#AiToolsStatusBar {
    background-color: #1a1a22;
    border-radius: 4px;
    padding: 2px 4px;
}
QLabel#AiToolsSummary {
    color: #9a9aa5;
    font-size: 11px;
    padding: 4px 6px;
}
QLabel#AiToolsMeta {
    color: #a0a0a8;
    font-size: 12px;
}
QLabel#AiToolsSection {
    color: #4a9eff;
    font-size: 12px;
    font-weight: bold;
    margin-top: 4px;
}
QLabel#AiToolsEmpty {
    color: #6a6a72;
    font-size: 12px;
    padding-left: 4px;
}
QScrollArea#AiToolsScroll {
    border: none;
    background-color: transparent;
}
QFrame#AiToolsCard_ready {
    background-color: #1a2420;
    border: 1px solid #2a5a3a;
    border-radius: 6px;
}
QFrame#AiToolsCard_missing_env {
    background-color: #2a2418;
    border: 1px solid #6a5020;
    border-radius: 6px;
}
QFrame#AiToolsCard_connect_failed {
    background-color: #2a1818;
    border: 1px solid #6a3030;
    border-radius: 6px;
}
QFrame#AiToolsCard_disabled {
    background-color: #1e1e24;
    border: 1px solid #333;
    border-radius: 6px;
}
QLabel#AiToolsCardTitle {
    color: #e0e0e0;
    font-size: 13px;
    font-weight: bold;
}
QLabel#AiToolsCardDetail {
    color: #9a9aa5;
    font-size: 11px;
}
QLabel#AiToolsBadge_ready {
    color: #6fcf97;
    font-size: 11px;
}
QLabel#AiToolsBadge_missing_env {
    color: #f2c94c;
    font-size: 11px;
}
QLabel#AiToolsBadge_connect_failed {
    color: #ff8a8a;
    font-size: 11px;
}
QLabel#AiToolsBadge_disabled {
    color: #6a6a72;
    font-size: 11px;
}
"""

INLINE_TRACE_STYLESHEET = """
QFrame#AiInlineTraceBlock {
    background-color: #17171e;
    border: 1px solid #2a2a34;
    border-radius: 8px;
}
QLabel#AiInlineTraceHeader {
    color: #a8a8b2;
    font-size: 11px;
}
QPushButton#AiInlineTraceStep {
    color: #c8c8d0;
    font-size: 11px;
    text-align: left;
    padding: 2px 4px;
    border: none;
}
QPushButton#AiInlineTraceStep:hover {
    color: #e8e8ec;
    background-color: #22222c;
    border-radius: 4px;
}
QPushButton#AiInlineTraceStep[stepStatus="running"] {
    color: #4a9eff;
}
QPushButton#AiInlineTraceStep[stepStatus="error"] {
    color: #ff8a8a;
}
QPlainTextEdit#AiInlineTraceDetail {
    background-color: #101016;
    border: 1px solid #2a2a32;
    border-radius: 4px;
    color: #b0b0b8;
    font-family: Menlo, Monaco, Consolas, monospace;
    font-size: 10px;
    padding: 6px;
}
"""
