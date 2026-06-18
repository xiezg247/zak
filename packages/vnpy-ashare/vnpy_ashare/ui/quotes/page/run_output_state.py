"""运行输出面板状态（与 splitter 解耦，避免 run_log ↔ splitter 循环 import）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences._settings import get_settings

if TYPE_CHECKING:
    from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
    from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost

_RUN_OUTPUT_EXPANDED_KEY = "quotes/run_output/{page_name}/expanded"


def run_output_panel(page: WatchlistHost) -> TaskRunOutputPanel | None:
    if not page.config.show_run_output_panel:
        return None
    panel = getattr(page, "run_output_panel", None)
    return panel


def _settings() -> QtCore.QSettings:
    return get_settings()


def _coerce_settings_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_run_output_expanded(page_name: str) -> bool:
    settings = _settings()
    return _coerce_settings_bool(
        settings.value(_RUN_OUTPUT_EXPANDED_KEY.format(page_name=page_name)),
        default=False,
    )


def save_run_output_expanded(page_name: str, expanded: bool) -> None:
    settings = _settings()
    settings.setValue(_RUN_OUTPUT_EXPANDED_KEY.format(page_name=page_name), expanded)
