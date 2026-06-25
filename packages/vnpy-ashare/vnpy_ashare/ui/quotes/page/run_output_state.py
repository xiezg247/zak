"""运行输出面板状态（与 splitter 解耦，避免 run_log ↔ splitter 循环 import）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui
from vnpy_ashare.config.preferences._settings import coerce_settings_bool

if TYPE_CHECKING:
    from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
    from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


def _run_output_expanded_key(page_name: str) -> str:
    return f"quotes/run_output/{page_name}/expanded"


def run_output_panel(page: WatchlistHost) -> TaskRunOutputPanel | None:
    if not page.config.show_run_output_panel:
        return None
    panel = getattr(page, "run_output_panel", None)
    return panel


def load_run_output_expanded(page_name: str) -> bool:
    raw = load_scalar_local_ui(
        _run_output_expanded_key(page_name),
        load_default=lambda: False,
    )
    return coerce_settings_bool(raw, default=False)


def save_run_output_expanded(page_name: str, expanded: bool) -> None:
    save_scalar_local_ui(_run_output_expanded_key(page_name), expanded)
