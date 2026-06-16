"""雷达主区 Tab 偏好（QSettings）。"""

from __future__ import annotations

from typing import cast

from vnpy_ashare.quotes.radar.radar_catalog import RADAR_LAYOUT_SECTIONS, RadarCardMode

_SETTINGS_PREFIX = "quotes/radar/active_mode"
_DEFAULT_MODE: RadarCardMode = "statistical"
_VALID_MODES = frozenset(section.mode for section in RADAR_LAYOUT_SECTIONS)


def load_radar_board_mode() -> RadarCardMode:
    from vnpy.trader.ui import QtCore

    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    raw = str(settings.value(_SETTINGS_PREFIX, _DEFAULT_MODE) or _DEFAULT_MODE).strip()
    if raw in _VALID_MODES:
        return cast(RadarCardMode, raw)
    return _DEFAULT_MODE


def save_radar_board_mode(mode: RadarCardMode) -> None:
    from vnpy.trader.ui import QtCore

    if mode not in _VALID_MODES:
        return
    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    settings.setValue(_SETTINGS_PREFIX, mode)
