"""自选多维看盘 UI 设置。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiSortKey

ViewMode = Literal["table", "multiview"]

VIEW_MODE_KEY = "watchlist/multiview/view_mode"
SORT_KEY = "watchlist/multiview/sort_key"
GRID_COLUMNS_KEY = "watchlist/multiview/grid_columns"
DEFAULT_GRID_COLUMNS = 3


def _coerce_settings_str(value: object, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _coerce_settings_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(value, float):
        return int(value)
    return default


def load_view_mode() -> ViewMode:
    settings = get_settings()
    mode = _coerce_settings_str(settings.value(VIEW_MODE_KEY), default="table")
    return "multiview" if mode == "multiview" else "table"


def save_view_mode(mode: ViewMode) -> None:
    settings = get_settings()
    settings.setValue(VIEW_MODE_KEY, mode)


def load_sort_key() -> WatchlistMultiSortKey:
    settings = get_settings()
    key = _coerce_settings_str(settings.value(SORT_KEY), default="sort_order")
    if key in ("sort_order", "change_pct", "anomaly_score"):
        return key  # type: ignore[return-value]
    return "sort_order"


def save_sort_key(sort_key: WatchlistMultiSortKey) -> None:
    settings = get_settings()
    settings.setValue(SORT_KEY, sort_key)


def load_grid_columns() -> int:
    settings = get_settings()
    columns = _coerce_settings_int(settings.value(GRID_COLUMNS_KEY), default=DEFAULT_GRID_COLUMNS)
    return max(2, min(4, columns))


def save_grid_columns(columns: int) -> None:
    settings = get_settings()
    settings.setValue(GRID_COLUMNS_KEY, max(2, min(4, int(columns))))
