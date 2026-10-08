"""雷达自动刷新全量重算间隔（纯 UI，本机 QSettings）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._local_ui_pref import load_json_local_ui, save_json_local_ui

_LOCAL_UI_KEY = "radar/full_refresh_every"

# 自动刷新时每隔 N 次做一次全量重算（其余仅更新现价 / 涨幅）
_RADAR_FULL_REFRESH_EVERY: dict[str, int] = {
    "discovery_volume_surge": 5,
    "discovery_moneyflow_intraday": 5,
    "discovery_limit_ladder": 5,
    "watchlist_intraday": 5,
    "sector_theme": 3,
}


def default_full_refresh_every_n_ticks(card_id: str) -> int:
    return max(1, int(_RADAR_FULL_REFRESH_EVERY.get(card_id, 1)))


def _load_overrides() -> dict[str, int]:
    stored: dict[str, object] = load_json_local_ui(
        _LOCAL_UI_KEY,
        load_default=lambda: {},
    )
    if not isinstance(stored, dict):
        return {}
    overrides: dict[str, int] = {}
    for card_id, raw in stored.items():
        if not isinstance(raw, (int, float, str)):
            continue
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
