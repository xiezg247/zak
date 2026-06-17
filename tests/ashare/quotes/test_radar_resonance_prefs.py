"""雷达共振权重偏好测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_catalog import radar_card_resonance_weight
from vnpy_ashare.quotes.radar.radar_resonance_prefs import (
    SHORT_TERM_RADAR_RESONANCE_WEIGHTS,
    apply_short_term_radar_resonance_weights,
    load_radar_resonance_weights,
    reset_radar_resonance_weights_to_default,
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


def test_apply_short_term_preset() -> None:
    weights = apply_short_term_radar_resonance_weights()
    assert weights["leader_pick"] == SHORT_TERM_RADAR_RESONANCE_WEIGHTS["leader_pick"]
    assert weights["outlook_predict"] == 0.5
    reset_radar_resonance_weights_to_default()
