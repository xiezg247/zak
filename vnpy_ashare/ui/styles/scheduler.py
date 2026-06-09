"""QSS：SCHEDULER。"""

SCHEDULER_TABLE_STYLESHEET = """
QTableWidget#SchedulerTable {
    background-color: #1a1a1a;
    gridline-color: #2a2a2a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-size: 12px;
}
QTableWidget#SchedulerTable::item {
    padding: 6px 8px;
}
QTableWidget#SchedulerTable QPushButton#ActionButton,
QTableWidget#SchedulerTable QPushButton#SecondaryButton {
    padding: 4px 10px;
    font-size: 12px;
}
QTableWidget#SchedulerTable QHeaderView::section {
    background-color: #252525;
    color: #a0a0a0;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #333;
    font-size: 12px;
}
"""

SCHEDULER_PAGE_STYLESHEET = """
QLabel#SchedulerPageTitle {
    color: #e8e8e8;
    font-size: 16px;
    font-weight: 600;
}
QLabel#SchedulerHint {
    color: #6a6a7a;
    font-size: 12px;
}
QLabel#SchedulerSectionLabel {
    color: #8a8aaf;
    font-size: 12px;
    font-weight: 600;
}
QWidget#SchedulerPanel {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
}
QTextEdit#SchedulerLogView {
    background-color: #141418;
    border: none;
    color: #b8b8b8;
    font-family: Menlo, Monaco, "Courier New", monospace;
    font-size: 12px;
    padding: 10px 12px;
}
"""
