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


def test_board_quality_score_for_limit_up() -> None:
    from vnpy_ashare.quotes.radar.radar_leader import board_quality_score

    score = board_quality_score(
        {
            "symbol": "600000",
            "change_pct": 10.0,
            "limit_times": 1,
            "fd_amount": 30_000,
            "open_times": 0,
        }
    )
    assert score is not None
    assert score >= 80.0


def test_board_quality_score_none_for_normal_move() -> None:
    from vnpy_ashare.quotes.radar.radar_leader import board_quality_score

    assert board_quality_score({"symbol": "600000", "change_pct": 2.0}) is None
