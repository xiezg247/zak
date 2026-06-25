"""自选页布局预设（纯 UI，本机 QSettings，按 user_id 隔离）。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui
from vnpy_ashare.config.preferences._settings import get_settings

LayoutPresetId = Literal["intraday", "review"]

LAYOUT_PRESET_KEY = "quotes/watchlist/layout_preset_v1"
_LOCAL_UI_KEY = "watchlist/layout_preset_v1"
DEFAULT_LAYOUT_PRESET: LayoutPresetId = "intraday"


def _load_preset_from_legacy() -> LayoutPresetId:
    value = str(get_settings().value(LAYOUT_PRESET_KEY, DEFAULT_LAYOUT_PRESET) or "").strip()
    if value in ("intraday", "review"):
        return value  # type: ignore[return-value]
    return DEFAULT_LAYOUT_PRESET


def load_watchlist_layout_preset() -> LayoutPresetId:
    value = str(
        load_scalar_local_ui(
            _LOCAL_UI_KEY,
            load_default=_load_preset_from_legacy,
        )
        or DEFAULT_LAYOUT_PRESET
    ).strip()
    if value in ("intraday", "review"):
        return value  # type: ignore[return-value]
    return DEFAULT_LAYOUT_PRESET


def save_watchlist_layout_preset(preset_id: LayoutPresetId) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, preset_id)
