"""雷达自动刷新全量重算间隔（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_json_local_ui, save_json_local_ui
from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.quotes.radar.radar_catalog_defaults import RADAR_FULL_REFRESH_EVERY

_KEY_PREFIX = "quotes/radar/full_refresh_every/"
_LOCAL_UI_KEY = "radar/full_refresh_every"


def default_full_refresh_every_n_ticks(card_id: str) -> int:
    return max(1, int(RADAR_FULL_REFRESH_EVERY.get(card_id, 1)))


def _load_all_from_qsettings() -> dict[str, int]:
    settings = get_settings()
    payload: dict[str, int] = {}
    for card_id in RADAR_FULL_REFRESH_EVERY:
        raw = settings.value(f"{_KEY_PREFIX}{card_id}")
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        payload[card_id] = max(1, min(value, 20))
    return payload


def _load_overrides() -> dict[str, int]:
    stored = load_json_local_ui(
        _LOCAL_UI_KEY,
        load_default=_load_all_from_qsettings,
    )
    if not isinstance(stored, dict):
        return {}
    overrides: dict[str, int] = {}
    for card_id, raw in stored.items():
        try:
            overrides[str(card_id)] = max(1, min(int(raw), 20))
        except (TypeError, ValueError):
            continue
    return overrides


def load_radar_full_refresh_every(card_id: str) -> int:
    overrides = _load_overrides()
    if card_id in overrides:
        return overrides[card_id]
    return default_full_refresh_every_n_ticks(card_id)


def save_radar_full_refresh_every(card_id: str, every_n: int) -> None:
    overrides = _load_overrides()
    overrides[card_id] = max(1, min(int(every_n), 20))
    save_json_local_ui(_LOCAL_UI_KEY, overrides)


def full_refresh_every_n_ticks(card_id: str) -> int:
    return load_radar_full_refresh_every(card_id)
