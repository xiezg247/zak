"""AI 面板样式。"""

PANEL_STYLESHEET = """
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
QLabel#AiBubbleUser {
    background-color: #2a3a55;
    color: #e8e8e8;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
}
QLabel#AiBubbleAssistant {
    background-color: #1e1e24;
    color: #e0e0e0;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
}
QLabel#AiBubbleError {
    background-color: #3a2020;
    color: #ff8a8a;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
}
QPlainTextEdit#AiInput {
    background-color: #1e1e24;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px;
    color: #e0e0e0;
    font-size: 13px;
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
QLabel#AiTitle {
    font-size: 14px;
    font-weight: bold;
    color: #e0e0e0;
}
QLabel#AiConfigHint {
    font-size: 11px;
    color: #6a6a72;
}
"""
