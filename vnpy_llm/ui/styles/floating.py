"""AI 浮动聊天窗口 QSS。

``FLOATING_CHAT_STYLESHEET``：外框 + 标题栏 + quick_action；
``FLOATING_CHAT_INNER_STYLESHEET``：内嵌聊天区（气泡样式与侧栏 panel 略有差异）。
"""

from vnpy_llm.ui.styles.quick_action import QUICK_ACTION_STYLESHEET

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
    + QUICK_ACTION_STYLESHEET
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
