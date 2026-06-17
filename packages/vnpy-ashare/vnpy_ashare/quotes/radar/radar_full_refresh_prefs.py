"""雷达自动刷新全量重算间隔（QSettings，可覆盖内置默认）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.quotes.radar.radar_catalog_defaults import RADAR_FULL_REFRESH_EVERY

_SETTINGS = get_settings()
_KEY_PREFIX = "quotes/radar/full_refresh_every/"


def default_full_refresh_every_n_ticks(card_id: str) -> int:
    return max(1, int(RADAR_FULL_REFRESH_EVERY.get(card_id, 1)))


def load_radar_full_refresh_every(card_id: str) -> int:
    raw = _SETTINGS.value(f"{_KEY_PREFIX}{card_id}")
    if raw is None:
        return default_full_refresh_every_n_ticks(card_id)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default_full_refresh_every_n_ticks(card_id)
    return max(1, min(value, 20))


def save_radar_full_refresh_every(card_id: str, every_n: int) -> None:
    value = max(1, min(int(every_n), 20))
    _SETTINGS.setValue(f"{_KEY_PREFIX}{card_id}", value)


def full_refresh_every_n_ticks(card_id: str) -> int:
    return load_radar_full_refresh_every(card_id)
