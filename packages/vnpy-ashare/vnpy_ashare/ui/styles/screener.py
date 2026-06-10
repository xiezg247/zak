"""QSS：SCREENER。"""

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

QLabel#ScreenerEmptyResult {
    color: #5a5a6a;
    font-size: 13px;
    padding: 24px;
}

QLabel#ScreenerRunSummary {
    color: #9a9ab8;
    font-size: 12px;
    padding: 4px 2px;
    line-height: 1.4;
}

QPlainTextEdit#ScreenerRunLogView {
    background-color: #141418;
    border: 1px solid #2a2a30;
    border-radius: 4px;
    color: #a8a8b0;
    font-family: Menlo, Monaco, "Courier New", monospace;
    font-size: 11px;
    padding: 8px 10px;
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
QTableWidget#MarketTable::item,
QTableView#MarketTable::item {
    padding: 5px 4px;
}
QTableWidget#MarketTable::item:selected,
QTableView#MarketTable::item:selected {
    background-color: #2a4a7a;
}
QTableWidget#MarketTable::item:hover,
QTableView#MarketTable::item:hover {
    background-color: #242428;
}
QTableWidget#MarketTable::item:alternate,
QTableView#MarketTable::item:alternate {
    background-color: #1e1e22;
}

QScrollBar#MarketTableScroll:vertical {
    background-color: #3a3a48;
    width: 18px;
    margin: 0;
    border: none;
    border-left: 1px solid #5a8fd8;
}
QScrollBar#MarketTableScroll::handle:vertical {
    background-color: #8a96aa;
    min-height: 52px;
    border-radius: 9px;
    margin: 3px;
    border: 1px solid #b8c4d8;
}
QScrollBar#MarketTableScroll::handle:vertical:hover {
    background-color: #4a9eff;
    border-color: #8ec0ff;
}
QScrollBar#MarketTableScroll::handle:vertical:pressed {
    background-color: #2a6fbf;
    border-color: #4a9eff;
}
QScrollBar#MarketTableScroll::add-page:vertical,
QScrollBar#MarketTableScroll::sub-page:vertical {
    background: #2d2d38;
}
QScrollBar#MarketTableScroll::add-line:vertical,
QScrollBar#MarketTableScroll::sub-line:vertical {
    background: none;
    height: 0;
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

/* ── 市场页表格加载遮罩 ── */
QWidget#MarketTableLoading {
    background-color: rgba(18, 18, 20, 0.72);
}
QWidget#MarketTableLoadingPanel {
    background-color: #1e1e24;
    border: 1px solid #3a3a44;
    border-radius: 8px;
}
QLabel#MarketTableLoadingLabel {
    color: #c8c8d8;
    font-size: 13px;
}
QProgressBar#MarketTableLoadingBar {
    background-color: #2a2a32;
    border: 1px solid #3a3a44;
    border-radius: 4px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
}
QProgressBar#MarketTableLoadingBar::chunk {
    background-color: #4a9eff;
    border-radius: 3px;
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

QTabBar#ScreenerRunFilterTabs {
    background-color: transparent;
}
QTabBar#ScreenerRunFilterTabs::tab {
    background-color: #252525;
    color: #9090a0;
    border: 1px solid #3a3a3a;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 12px;
    margin-right: 2px;
    font-size: 11px;
}
QTabBar#ScreenerRunFilterTabs::tab:selected {
    background-color: #1e1e22;
    color: #e0e0e0;
    border-color: #4a4a4a;
}
QTabBar#ScreenerRunFilterTabs::tab:hover {
    color: #c8c8c8;
}

QLabel#ScreenerUnreadBadge {
    background-color: #4a9eff;
    color: #ffffff;
    border-radius: 8px;
    font-size: 10px;
    font-weight: bold;
    min-width: 16px;
    max-width: 24px;
    min-height: 16px;
    padding: 0 4px;
}

QListWidget#AiSessionListWidget::item {
    padding: 0;
    border-radius: 6px;
    margin: 2px 0;
}
QListWidget#AiSessionListWidget::item:selected,
QListWidget#AiSessionListWidget::item:hover {
    background-color: transparent;
}
QFrame#ScreenerRunRow {
    background-color: transparent;
    border-radius: 6px;
    border-left: 3px solid transparent;
}
QFrame#ScreenerRunRow[active="true"] {
    background-color: #1a2438;
    border-left: 3px solid #4a9eff;
}
QFrame#ScreenerRunRow:hover {
    background-color: #1e1e28;
}
QLabel#ScreenerRunRowTitle {
    color: #d0d0d8;
    font-size: 12px;
    min-height: 16px;
}
QLabel#ScreenerRunRowSubtitle {
    color: #6a6a72;
    font-size: 10px;
    min-height: 14px;
}
QCheckBox#ScreenerRunCheck {
    spacing: 0;
}
QCheckBox#ScreenerRunCheck::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #4a4a55;
    border-radius: 3px;
    background-color: #1a1a22;
}
QCheckBox#ScreenerRunCheck::indicator:checked {
    background-color: #4a9eff;
    border-color: #4a9eff;
}
"""
