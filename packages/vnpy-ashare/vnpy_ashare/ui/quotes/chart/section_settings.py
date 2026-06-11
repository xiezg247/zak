"""K 线区折叠状态（QSettings）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore

SETTINGS_ORG = "vnpy_ashare"
SETTINGS_APP = "ZakTerminal"
CHART_SECTION_EXPANDED_PREFIX = "quotes/chart_section/expanded/"


def _settings() -> QtCore.QSettings:
    return QtCore.QSettings(SETTINGS_ORG, SETTINGS_APP)


def _expanded_key(page_name: str) -> str:
    return f"{CHART_SECTION_EXPANDED_PREFIX}{page_name}"


def load_chart_section_expanded(page_name: str, *, default: bool = True) -> bool:
    settings = _settings()
    raw = settings.value(_expanded_key(page_name), default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def save_chart_section_expanded(page_name: str, expanded: bool) -> None:
    _settings().setValue(_expanded_key(page_name), expanded)
