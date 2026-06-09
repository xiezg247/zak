"""AI 快捷操作 chips / 菜单 QSS。"""

QUICK_ACTION_STYLESHEET = """
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
