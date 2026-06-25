"""K 线区折叠状态（QSettings）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui
from vnpy_ashare.config.preferences._settings import coerce_settings_bool

CHART_SECTION_EXPANDED_PREFIX = "quotes/chart_section/expanded/"


def _expanded_key(page_name: str) -> str:
    return f"{CHART_SECTION_EXPANDED_PREFIX}{page_name}"


def load_chart_section_expanded(page_name: str, *, default: bool = True) -> bool:
    raw = load_scalar_local_ui(_expanded_key(page_name), load_default=lambda: default)
    return coerce_settings_bool(raw, default=default)


def save_chart_section_expanded(page_name: str, expanded: bool) -> None:
    save_scalar_local_ui(_expanded_key(page_name), expanded)
