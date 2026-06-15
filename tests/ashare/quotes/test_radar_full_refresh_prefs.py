"""雷达全量重算间隔偏好测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_catalog import full_refresh_every_n_ticks
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import (
    load_radar_full_refresh_every,
    save_radar_full_refresh_every,
)


def test_save_and_load_full_refresh_every() -> None:
    save_radar_full_refresh_every("discovery_volume_surge", 10)
    assert load_radar_full_refresh_every("discovery_volume_surge") == 10
    assert full_refresh_every_n_ticks("discovery_volume_surge") == 10
