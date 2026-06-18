"""自选页布局预设 QSettings。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.config.preferences._settings import get_settings

LayoutPresetId = Literal["intraday", "register", "review"]

LAYOUT_PRESET_KEY = "quotes/watchlist/layout_preset_v1"
DEFAULT_LAYOUT_PRESET: LayoutPresetId = "intraday"


def load_watchlist_layout_preset() -> LayoutPresetId:
    value = str(get_settings().value(LAYOUT_PRESET_KEY, DEFAULT_LAYOUT_PRESET) or "").strip()
    if value in ("intraday", "register", "review"):
        return value  # type: ignore[return-value]
    return DEFAULT_LAYOUT_PRESET


def save_watchlist_layout_preset(preset_id: LayoutPresetId) -> None:
    get_settings().setValue(LAYOUT_PRESET_KEY, preset_id)
