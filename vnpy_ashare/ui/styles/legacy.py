"""QSS：LEGACY_PAGE。"""

LEGACY_PAGE_STYLESHEET = """
QWidget#BacktestPage,
QWidget#DataManagerPage {
    background-color: #1a1a1a;
    color: #e0e0e0;
}
QWidget#BacktestPage QLabel,
QWidget#DataManagerPage QLabel {
    color: #b0b0b0;
    font-size: 12px;
}
QWidget#BacktestPage QLineEdit#BacktestInput,
QWidget#BacktestPage QDateEdit#BacktestInput,
QWidget#DataManagerPage QLineEdit {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #f0f0f0;
    min-height: 26px;
    font-size: 13px;
}
QWidget#BacktestPage QLineEdit#BacktestInput:focus,
QWidget#BacktestPage QDateEdit#BacktestInput:focus {
    border-color: #4a9eff;
}
QWidget#BacktestPage QDateEdit#BacktestInput::drop-down,
QWidget#BacktestPage QDateEdit#BacktestInput::down-arrow {
    border: none;
}
QTextEdit#BacktestLogView {
    background-color: #141418;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    color: #b8b8b8;
    font-family: Menlo, Monaco, "Courier New", monospace;
    font-size: 12px;
}
QTableWidget#BacktestStatisticsTable,
QTreeWidget#DataManagerTree,
QTableWidget#DataManagerTable {
    background-color: #1a1a1a;
    gridline-color: #2a2a2a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-size: 12px;
    color: #e0e0e0;
    alternate-background-color: #1e1e22;
}
QTableWidget#BacktestStatisticsTable::item,
QTreeWidget#DataManagerTree::item,
QTableWidget#DataManagerTable::item {
    padding: 4px 6px;
}
QHeaderView::section {
    background-color: #252525;
    color: #a0a0a0;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #333;
    font-size: 12px;
}
QListWidget#BatchSessionListWidget {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 4px;
    outline: none;
    color: #d0d0d8;
    font-size: 12px;
}
QListWidget#BatchSessionListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #252528;
}
QListWidget#BatchSessionListWidget::item:selected {
    background-color: #2a4a7a;
    color: #ffffff;
}
QListWidget#BatchSessionListWidget::item:hover {
    background-color: #242428;
}
QGroupBox#BacktestFormBox {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
    margin-top: 4px;
    padding: 14px 12px 12px 12px;
    font-size: 12px;
    color: #a0a0a0;
}
QGroupBox#BacktestFormBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #8a8aaf;
    font-weight: bold;
}
QWidget#BacktestChartFrame {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
}
QFormLayout QLabel {
    color: #9a9aa5;
    font-size: 12px;
}
"""


_PRIMARY_ACTION_LABELS = frozenset({"开始回测"})


def apply_legacy_page_style(widget, *, page_id: str) -> None:
    """vnpy 继承页：深色表单 / 表格 / 日志。"""
    from vnpy_ashare.ui.styles.compose import TERMINAL_STYLESHEET

    widget.setObjectName(page_id)
    widget.setStyleSheet(TERMINAL_STYLESHEET + LEGACY_PAGE_STYLESHEET)


def style_legacy_form_inputs(widget, *, input_name: str = "BacktestInput") -> None:
    from vnpy.trader.ui import QtWidgets

    for line in widget.findChildren(QtWidgets.QLineEdit):
        if line.objectName() in ("SearchBox", "PageJumpInput", "BacktestInput"):
            continue
        line.setObjectName(input_name)
    for date_edit in widget.findChildren(QtWidgets.QDateEdit):
        date_edit.setObjectName(input_name)


def style_legacy_push_buttons(
    widget,
    *,
    primary_labels: frozenset[str] = _PRIMARY_ACTION_LABELS,
    skip: frozenset[str] = frozenset({"SecondaryButton", "ActionButton", "PrimaryRunButton", "DangerButton"}),
) -> None:
    from vnpy.trader.ui import QtWidgets

    for btn in widget.findChildren(QtWidgets.QPushButton):
        name = btn.objectName()
        if name in skip:
            continue
        if btn.text().strip() in primary_labels:
            btn.setObjectName("ActionButton")
        else:
            btn.setObjectName("SecondaryButton")


def apply_toolbar_combo_style(combo) -> None:
    """工具栏下拉：深色背景 + 高对比选项（macOS 需自定义 QListView）。"""
    from vnpy.trader.ui import QtWidgets

    combo.setObjectName("ToolbarCombo")
    view = QtWidgets.QListView(combo)
    view.setObjectName("ToolbarComboList")
    combo.setView(view)
    combo.setMinimumContentsLength(5)


def apply_settings_combo_style(combo) -> None:
    """配置页下拉：macOS 深色选项列表。"""
    from vnpy.trader.ui import QtWidgets

    combo.setObjectName("SettingsInput")
    view = QtWidgets.QListView(combo)
    view.setObjectName("SettingsComboList")
    combo.setView(view)
    combo.setMinimumContentsLength(8)
