"""AI 聊天气泡 QSS（侧栏面板）。"""

CHAT_BUBBLE_STYLESHEET = """
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
