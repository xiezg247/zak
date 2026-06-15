"""雷达共振权重偏好测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_catalog import radar_card_resonance_weight
from vnpy_ashare.quotes.radar.radar_resonance_prefs import (
    load_radar_resonance_weights,
    save_radar_resonance_weights,
)


def test_save_and_load_resonance_weights() -> None:
    save_radar_resonance_weights(
        {
            "discovery_volume_surge": 3.0,
            "screen_latest": 0.5,
        }
    )
    weights = load_radar_resonance_weights()
    assert weights["discovery_volume_surge"] == 3.0
    assert weights["screen_latest"] == 0.5
    assert radar_card_resonance_weight("discovery_volume_surge") == 3.0
