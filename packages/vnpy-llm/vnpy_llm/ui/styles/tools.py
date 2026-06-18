"""AI 工具状态卡片 QSS。"""

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
QFrame#AiToolsCard_disabled,
QFrame#AiToolsCard_idle {
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
QLabel#AiToolsBadge_disabled,
QLabel#AiToolsBadge_idle {
    color: #6a6a72;
    font-size: 11px;
}
"""
