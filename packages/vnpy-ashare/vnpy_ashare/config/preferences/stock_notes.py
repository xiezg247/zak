"""看盘页个股笔记 UI 偏好。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui
from vnpy_ashare.config.preferences._settings import coerce_settings_bool

STOCK_NOTE_PANEL_EXPANDED_KEY = "watchlist/stock_note_panel/expanded"
STOCK_NOTE_ACTIVE_TAB_KEY = "watchlist/stock_note_panel/active_tab"
STOCK_NOTE_QUICK_TAB_KEY = "watchlist/stock_note_panel/quick_tab"

STOCK_NOTE_PANEL_DEFAULT_HEIGHT = 200
STOCK_NOTE_PANEL_COLLAPSED_HEIGHT = 32

TAB_MEMO = "memo"
TAB_ENTRY = "entry"


def _normalize_tab(value: object, *, default: str) -> str:
    text = str(value or default).strip()
    return text if text in {TAB_MEMO, TAB_ENTRY} else default


def load_stock_note_panel_expanded() -> bool:
    raw = load_scalar_local_ui(STOCK_NOTE_PANEL_EXPANDED_KEY, load_default=lambda: True)
    return coerce_settings_bool(raw, default=True)


def save_stock_note_panel_expanded(expanded: bool) -> None:
    save_scalar_local_ui(STOCK_NOTE_PANEL_EXPANDED_KEY, expanded)


def load_stock_note_active_tab() -> str:
    raw = load_scalar_local_ui(STOCK_NOTE_ACTIVE_TAB_KEY, load_default=lambda: TAB_ENTRY)
    return _normalize_tab(raw, default=TAB_ENTRY)


def save_stock_note_active_tab(tab: str) -> None:
    save_scalar_local_ui(STOCK_NOTE_ACTIVE_TAB_KEY, _normalize_tab(tab, default=TAB_ENTRY))


def load_stock_note_quick_tab() -> str:
    raw = load_scalar_local_ui(STOCK_NOTE_QUICK_TAB_KEY, load_default=lambda: TAB_ENTRY)
    return _normalize_tab(raw, default=TAB_ENTRY)


def save_stock_note_quick_tab(tab: str) -> None:
    save_scalar_local_ui(STOCK_NOTE_QUICK_TAB_KEY, _normalize_tab(tab, default=TAB_ENTRY))
