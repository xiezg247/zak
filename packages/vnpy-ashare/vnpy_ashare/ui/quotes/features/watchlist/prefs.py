"""自选页布局预设（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from typing import Literal

from vnpy_ashare.config.preferences._local_ui_pref import load_scalar_local_ui, save_scalar_local_ui

LayoutPresetId = Literal["intraday", "review"]

_LOCAL_UI_KEY = "watchlist/layout_preset_v1"
DEFAULT_LAYOUT_PRESET: LayoutPresetId = "intraday"


def load_watchlist_layout_preset() -> LayoutPresetId:
    value = str(
        load_scalar_local_ui(
            _LOCAL_UI_KEY,
            load_default=lambda: DEFAULT_LAYOUT_PRESET,
        )
        or DEFAULT_LAYOUT_PRESET
    ).strip()
    if value in ("intraday", "review"):
        return value  # type: ignore[return-value]
    return DEFAULT_LAYOUT_PRESET


def save_watchlist_layout_preset(preset_id: LayoutPresetId) -> None:
    save_scalar_local_ui(_LOCAL_UI_KEY, preset_id)
