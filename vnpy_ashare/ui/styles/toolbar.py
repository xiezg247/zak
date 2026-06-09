"""QSS：TOOLBAR_COMBO。"""

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
