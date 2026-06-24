"""QSS：TERMINAL_BASE。"""

TERMINAL_STYLESHEET = """
QWidget#MarketRoot {
    background-color: #1a1a1a;
}
QWidget#SidebarNav {
    background-color: #0f0f12;
    border-right: none;
}
QSplitter#MainNavSplitter {
    background-color: #0f0f12;
}
QSplitter#MainNavSplitter::handle {
    background-color: #252528;
}
QSplitter#MainNavSplitter::handle:hover {
    background-color: #4a9eff;
}
QScrollArea#NavScroll {
    background-color: #0f0f12;
    border: none;
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
    background-color: #1a2438;
    color: #4a9eff;
}
QWidget#NavBody {
    background-color: transparent;
}
QWidget#NavGroupSpacer {
    background-color: transparent;
    margin: 2px 0;
}
QTableWidget#MarketTable,
QTableView#MarketTable {
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
QPushButton#DangerButton {
    background-color: #2a2020;
    border: 1px solid #6a3030;
    border-radius: 4px;
    padding: 4px 14px;
    color: #ff8a8a;
    font-size: 12px;
}
QPushButton#DangerButton:hover {
    background-color: #3a2828;
    border-color: #8a4040;
    color: #ffaaaa;
}
QLabel#PageTitle {
    color: #e8e8e8;
    font-size: 16px;
    font-weight: 600;
}
QLabel#PageHint {
    color: #6a6a7a;
    font-size: 12px;
}
QLabel#BottomBarMeta {
    color: #8a8a8a;
    font-size: 12px;
}
QLabel#StatsLabel,
QLabel#QuoteSubInfo {
    color: #8a8a8a;
    font-size: 12px;
    padding: 2px 6px;
}
QWidget#QuotesToolbarHost {
    background-color: transparent;
}
QFrame#DepthPanel {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
}
QFrame#DepthPanel QLabel {
    color: #a0a0a0;
    font-size: 12px;
}
QFrame#DepthPanel QTableWidget,
QFrame#DepthPanel QTableWidget#DepthTable {
    background-color: #1a1a1a;
    border: none;
    font-size: 12px;
    color: #d0d0d0;
}
QWidget#DiagnosePanel {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
    padding: 4px;
}
QLabel#SectionLabel {
    color: #8a8aaf;
    font-size: 12px;
    font-weight: bold;
}
QLabel#DiagnoseBody {
    color: #8a8a8a;
    font-size: 12px;
}
QFrame#FeedItemCard {
    background-color: #1a1a1e;
    border: 1px solid #2a2a30;
    border-radius: 6px;
}
QLabel#FeedItemHeader {
    color: #8a8a8a;
    font-size: 11px;
}
QLabel#FeedItemTitle {
    color: #e8e8e8;
    font-size: 13px;
    font-weight: 600;
}
QLabel#FeedItemDetail {
    color: #a8a8b8;
    font-size: 12px;
    line-height: 1.4;
}
"""
