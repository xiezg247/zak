"""券商终端风格配色（A 股：涨红跌绿）"""

RISE_COLOR = "#ff4d4f"
FALL_COLOR = "#3ddc84"
FLAT_COLOR = "#c8c8c8"
HEADER_BG = "#2a2a2a"
PANEL_BG = "#1e1e1e"
ACCENT_COLOR = "#4a9eff"
NAV_MUTED_COLOR = "#6a6a6a"

TERMINAL_STYLESHEET = """
QWidget#MarketRoot {
    background-color: #1a1a1a;
}
QWidget#SidebarNav {
    background-color: #0f0f12;
    border-right: 1px solid #252528;
}
QToolButton#NavButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #8a8a8a;
    padding: 10px 4px;
    margin: 2px 6px;
    font-size: 12px;
}
QToolButton#NavButton:hover {
    background-color: #1c1c22;
    color: #b8b8b8;
}
QToolButton#NavButton:checked {
    background-color: transparent;
    color: #4a9eff;
}
QTableWidget#MarketTable {
    background-color: #1a1a1a;
    gridline-color: #2a2a2a;
    border: none;
    font-size: 12px;
}
QHeaderView::section {
    background-color: #252525;
    color: #a0a0a0;
    padding: 6px 4px;
    border: none;
    border-right: 1px solid #333;
    font-size: 12px;
}
QLineEdit#SearchBox {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
}
QLabel#QuoteHeader {
    font-size: 22px;
    font-weight: bold;
}
QLabel#IndexTicker {
    background-color: #141414;
    color: #d0d0d0;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 14px;
    color: #e0e0e0;
}
QPushButton:hover {
    background-color: #3a3a3a;
}
QPushButton:disabled {
    color: #666;
}
QPushButton#ActionButton {
    background-color: #2a5a9e;
    border: 1px solid #4a9eff;
    border-radius: 4px;
    padding: 4px 14px;
    color: #ffffff;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#ActionButton:hover {
    background-color: #3a6fbf;
    border-color: #6ab4ff;
}
QPushButton#ActionButton:pressed {
    background-color: #1e4a80;
}
QPushButton#SecondaryButton {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 14px;
    color: #b0b0b0;
    font-size: 12px;
}
QPushButton#SecondaryButton:hover {
    background-color: #353535;
    border-color: #555;
    color: #e0e0e0;
}
QPushButton#SecondaryButton:pressed {
    background-color: #222;
}
"""

TOOLBAR_COMBO_STYLESHEET = """
QComboBox#ToolbarCombo {
    background-color: #252525;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    color: #f0f0f0;
    padding: 6px 10px;
    padding-right: 26px;
    font-size: 13px;
    min-width: 76px;
}
QComboBox#ToolbarCombo:hover {
    border-color: #5a8fd4;
    background-color: #2c2c2c;
}
QComboBox#ToolbarCombo:focus {
    border-color: #4a9eff;
}
QComboBox#ToolbarCombo:disabled {
    color: #777777;
    background-color: #1f1f1f;
}
QComboBox#ToolbarCombo::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
}
QComboBox#ToolbarCombo::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox#ToolbarCombo QAbstractItemView {
    background-color: #2a2a2a;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    selection-background-color: #3d6a9e;
    selection-color: #ffffff;
    outline: none;
    padding: 4px 0;
}
QComboBox#ToolbarCombo QAbstractItemView::item {
    min-height: 32px;
    padding: 6px 14px;
    color: #f0f0f0;
}
QComboBox#ToolbarCombo QAbstractItemView::item:hover {
    background-color: #383838;
    color: #ffffff;
}
QComboBox#ToolbarCombo QAbstractItemView::item:selected {
    background-color: #3d6a9e;
    color: #ffffff;
}
"""

TERMINAL_STYLESHEET = TERMINAL_STYLESHEET + TOOLBAR_COMBO_STYLESHEET


def apply_toolbar_combo_style(combo) -> None:
    """工具栏下拉：深色背景 + 高对比选项（macOS 需自定义 QListView）。"""
    from vnpy.trader.ui import QtWidgets

    combo.setObjectName("ToolbarCombo")
    view = QtWidgets.QListView(combo)
    view.setObjectName("ToolbarComboList")
    combo.setView(view)
    combo.setMinimumContentsLength(5)
