"""leader_score 情绪阶段权重测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_leader import leader_score_weights_for_stage


def test_stage_weights_normalized() -> None:
    for stage in ("startup", "climax", "divergence", None):
        weights = leader_score_weights_for_stage(stage)
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert set(weights) == {
            "limit_times",
            "seal_quality",
            "amount_rank",
            "seal_time",
            "net_mf",
            "sector_strength",
            "resonance",
        }


def test_startup_boosts_seal_time() -> None:
    base = leader_score_weights_for_stage(None)
    startup = leader_score_weights_for_stage("startup")
    assert startup["seal_time"] > base["seal_time"]
