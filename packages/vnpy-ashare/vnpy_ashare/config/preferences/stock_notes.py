"""看盘页个股笔记 QSettings。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings

STOCK_NOTE_PANEL_EXPANDED_KEY = "watchlist/stock_note_panel/expanded"
STOCK_NOTE_ACTIVE_TAB_KEY = "watchlist/stock_note_panel/active_tab"
STOCK_NOTE_QUICK_TAB_KEY = "watchlist/stock_note_panel/quick_tab"

STOCK_NOTE_PANEL_DEFAULT_HEIGHT = 200
STOCK_NOTE_PANEL_COLLAPSED_HEIGHT = 32

TAB_MEMO = "memo"
TAB_ENTRY = "entry"


def load_stock_note_panel_expanded() -> bool:
    settings = get_settings()
    return coerce_settings_bool(settings.value(STOCK_NOTE_PANEL_EXPANDED_KEY), default=True)


def save_stock_note_panel_expanded(expanded: bool) -> None:
    settings = get_settings()
    settings.setValue(STOCK_NOTE_PANEL_EXPANDED_KEY, expanded)


def load_stock_note_active_tab() -> str:
    settings = get_settings()
    value = str(settings.value(STOCK_NOTE_ACTIVE_TAB_KEY, TAB_ENTRY)).strip()
    return value if value in {TAB_MEMO, TAB_ENTRY} else TAB_ENTRY


def save_stock_note_active_tab(tab: str) -> None:
    settings = get_settings()
    settings.setValue(STOCK_NOTE_ACTIVE_TAB_KEY, tab if tab in {TAB_MEMO, TAB_ENTRY} else TAB_ENTRY)


def load_stock_note_quick_tab() -> str:
    settings = get_settings()
    value = str(settings.value(STOCK_NOTE_QUICK_TAB_KEY, TAB_ENTRY)).strip()
    return value if value in {TAB_MEMO, TAB_ENTRY} else TAB_ENTRY


def save_stock_note_quick_tab(tab: str) -> None:
    settings = get_settings()
    settings.setValue(STOCK_NOTE_QUICK_TAB_KEY, tab if tab in {TAB_MEMO, TAB_ENTRY} else TAB_ENTRY)
