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

SCHEDULER_TABLE_STYLESHEET = """
QTableWidget#SchedulerTable {
    background-color: #1a1a1a;
    gridline-color: #2a2a2a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-size: 12px;
}
QTableWidget#SchedulerTable::item {
    padding: 8px 10px;
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

SCREENER_STYLESHEET = """
/* ── 工具栏分隔线 ── */
QFrame#ToolbarSeparator {
    color: #3a3a3a;
    background-color: #3a3a3a;
}

/* ── 选股页表单面板 ── */
QGroupBox#ScreenerFormBox {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
    margin-top: 16px;
    padding: 14px 14px 10px 14px;
    font-size: 12px;
    color: #a0a0a0;
}
QGroupBox#ScreenerFormBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: #8a8aaf;
}

QLabel#ScreenerSectionLabel {
    color: #7a7a8f;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 0 2px 0;
}

QLabel#ScreenerHint {
    color: #6a6a7a;
    font-size: 11px;
    padding: 6px 4px;
}

/* ── 结果摘要 ── */
QLabel#ResultSummary {
    color: #8888aa;
    font-size: 12px;
    padding: 6px 2px;
}

/* ── 底部状态栏 ── */
QStatusBar#ScreenerStatusBar {
    background-color: #1a1a20;
    border-top: 1px solid #2a2a2a;
    color: #888;
    font-size: 12px;
    min-height: 28px;
}

/* ── 结果表格增强 ── */
QTableWidget#MarketTable::item {
    padding: 5px 4px;
}
QTableWidget#MarketTable::item:selected {
    background-color: #2a4a7a;
}
QTableWidget#MarketTable::item:hover {
    background-color: #242428;
}
QTableWidget#MarketTable::item:alternate {
    background-color: #1e1e22;
}

/* ── 主操作按钮 ── */
QPushButton#PrimaryRunButton {
    background-color: #2a5a9e;
    border: 1px solid #4a9eff;
    border-radius: 4px;
    padding: 6px 18px;
    color: #ffffff;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#PrimaryRunButton:hover {
    background-color: #3a6fbf;
    border-color: #6ab4ff;
}
QPushButton#PrimaryRunButton:pressed {
    background-color: #1e4a80;
}
QPushButton#PrimaryRunButton:disabled {
    background-color: #1a3a60;
    border-color: #3a5a80;
    color: #6688aa;
}

/* ── 底栏分页跳转输入框 ── */
QLineEdit#PageJumpInput {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 2px 6px;
    color: #e0e0e0;
    font-size: 12px;
    max-width: 48px;
}
QLineEdit#PageJumpInput:focus {
    border-color: #4a9eff;
}

/* ── 板块筛选下拉 ── */
QComboBox#BoardCombo {
    background-color: #252525;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    color: #f0f0f0;
    padding: 4px 10px;
    padding-right: 26px;
    font-size: 13px;
    min-width: 90px;
}
QComboBox#BoardCombo:hover {
    border-color: #5a8fd4;
    background-color: #2c2c2c;
}
QComboBox#BoardCombo:focus {
    border-color: #4a9eff;
}
QComboBox#BoardCombo:disabled {
    color: #777777;
    background-color: #1f1f1f;
}
QComboBox#BoardCombo::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
}
QComboBox#BoardCombo QAbstractItemView {
    background-color: #2a2a2a;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    selection-background-color: #3d6a9e;
    selection-color: #ffffff;
    outline: none;
    padding: 4px 0;
}
QComboBox#BoardCombo QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 12px;
    color: #f0f0f0;
}
QComboBox#BoardCombo QAbstractItemView::item:hover {
    background-color: #383838;
    color: #ffffff;
}
QComboBox#BoardCombo QAbstractItemView::item:selected {
    background-color: #3d6a9e;
    color: #ffffff;
}

/* ── 工具栏分组竖线 ── */
QFrame#ToolbarSeparator {
    color: #3a3a3a;
    background-color: #3a3a3a;
    max-width: 1px;
    min-width: 1px;
    margin: 2px 6px;
}
"""

SETTINGS_DIALOG_STYLESHEET = """
QDialog#SettingsDialog {
    background-color: #1a1a1a;
    color: #e0e0e0;
}
QScrollArea#SettingsScroll,
QWidget#SettingsScrollBody {
    background-color: transparent;
    border: none;
}
QLabel#SettingsHint {
    color: #8a8a95;
    font-size: 12px;
    padding: 8px 10px;
    background-color: #1e1e24;
    border: 1px solid #2d2d32;
    border-radius: 6px;
}
QLabel#SettingsMeta {
    color: #9a9aa5;
    font-size: 12px;
    margin-bottom: 4px;
}
QLabel#SettingsSubheading {
    color: #8a8aaf;
    font-size: 12px;
    font-weight: bold;
    margin-top: 4px;
}
QPushButton#SettingsSegmentLeft,
QPushButton#SettingsSegmentRight {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    padding: 6px 20px;
    color: #a0a0a8;
    font-size: 12px;
    min-width: 88px;
}
QPushButton#SettingsSegmentLeft {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
}
QPushButton#SettingsSegmentRight {
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QPushButton#SettingsSegmentLeft:checked,
QPushButton#SettingsSegmentRight:checked {
    background-color: #2a5a9e;
    border-color: #4a9eff;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#SettingsSegmentLeft:hover:!checked,
QPushButton#SettingsSegmentRight:hover:!checked {
    background-color: #2f2f2f;
    color: #d0d0d8;
}
QGroupBox#SettingsGroup {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-size: 12px;
    color: #a0a0a0;
}
QDialog#SettingsDialog QGroupBox#SettingsGroup {
    min-height: 48px;
}
QGroupBox#SettingsGroup::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #8a8aaf;
    font-weight: bold;
}
QTableWidget#SettingsEnvTable {
    background-color: #1a1a1a;
    gridline-color: #2a2a2a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-size: 12px;
    alternate-background-color: #1e1e22;
    selection-background-color: #2a4a7a;
    selection-color: #ffffff;
}
QTableWidget#SettingsEnvTable::item {
    padding-left: 10px;
    padding-right: 10px;
    border: none;
}
QTableWidget#SettingsEnvTable::item:alternate {
    background-color: #1e1e22;
}
QTableWidget#SettingsEnvTable::item:selected {
    background-color: #2a4a7a;
    color: #ffffff;
}
QTableWidget#SettingsEnvTable QHeaderView::section {
    background-color: #252525;
    color: #a0a0a0;
    padding-left: 10px;
    padding-right: 10px;
    border: none;
    border-bottom: 1px solid #333;
    border-right: 1px solid #333;
    font-size: 12px;
    min-height: 34px;
}
QLabel#SettingsFormLabel {
    color: #9a9aa5;
    font-size: 12px;
    min-width: 108px;
}
QSpinBox#SettingsInput {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #f0f0f0;
    min-height: 28px;
    font-size: 13px;
}
QSpinBox#SettingsInput::up-button,
QSpinBox#SettingsInput::down-button {
    width: 16px;
    background-color: #2d2d2d;
    border: none;
}
QLineEdit#SettingsInput,
QComboBox#SettingsInput {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 10px;
    color: #f0f0f0;
    min-height: 28px;
    font-size: 13px;
}
QLineEdit#SettingsInput:focus,
QComboBox#SettingsInput:focus {
    border-color: #4a9eff;
}
QLineEdit#SettingsInput:read-only {
    color: #a0a0a8;
    background-color: #1e1e22;
    border-color: #2d2d32;
}
QSpinBox#SettingsInput:focus {
    border-color: #4a9eff;
}
QComboBox#SettingsInput::drop-down {
    border: none;
    width: 22px;
}
QComboBox#SettingsInput QAbstractItemView {
    background-color: #2a2a2a;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    selection-background-color: #3d6a9e;
}
QCheckBox#SettingsCheck {
    color: #d8d8de;
    spacing: 8px;
}
QPushButton#SettingsPrimaryButton {
    background-color: #2a5a9e;
    border: 1px solid #4a9eff;
    border-radius: 4px;
    padding: 6px 18px;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#SettingsPrimaryButton:hover {
    background-color: #3a6fbf;
}
QPushButton#SettingsSecondaryButton {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 16px;
    color: #c8c8d0;
}
QPushButton#SettingsSecondaryButton:hover {
    background-color: #353535;
    color: #f0f0f0;
}
"""

TERMINAL_STYLESHEET = TERMINAL_STYLESHEET + TOOLBAR_COMBO_STYLESHEET + SCREENER_STYLESHEET


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
