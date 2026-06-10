"""AI 侧栏聊天面板 QSS。

组合顺序：面板骨架 → chat_bubble → 输入/按钮 → quick_action → 会话侧栏。
"""

from vnpy_llm.ui.styles.chat_bubble import CHAT_BUBBLE_STYLESHEET
from vnpy_llm.ui.styles.quick_action import QUICK_ACTION_STYLESHEET

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
    + CHAT_BUBBLE_STYLESHEET
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
    + QUICK_ACTION_STYLESHEET
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
QSplitter#AiPageSplitter::handle {
    background-color: #2a2a30;
}
QSplitter#AiPageSplitter::handle:hover {
    background-color: #4a9eff;
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
