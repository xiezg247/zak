"""龙头评分原语。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_leader import _seal_quality_proxy
from vnpy_ashare.quotes.radar.radar_leader_score import (
    amount_rank_in_group,
    board_quality_score,
    clamp01,
    norm_limit_times,
    seal_quality_proxy,
)


def test_seal_quality_proxy_public_and_compat_alias() -> None:
    row = {
        "vt_symbol": "600000.SSE",
        "limit_times": 1,
        "change_pct": 9.9,
        "amount": 2e8,
        "seal_strength_score": 0.0,
    }
    assert seal_quality_proxy(row) == _seal_quality_proxy(row)
    assert 0.0 <= seal_quality_proxy(row) <= 1.0


def test_norm_helpers() -> None:
    assert clamp01(1.5) == 1.0
    assert clamp01(-0.1) == 0.0
    assert norm_limit_times(0) == 0.2
    assert norm_limit_times(5) == 1.0


def test_amount_rank_in_group() -> None:
    ranks = amount_rank_in_group(
        [
            {"vt_symbol": "a", "amount": 100},
            {"vt_symbol": "b", "amount": 300},
            {"vt_symbol": "c", "amount": 200},
        ]
    )
    assert ranks["b"] >= ranks["c"] >= ranks["a"]


def test_board_quality_score_none_for_non_limit() -> None:
    assert board_quality_score({"vt_symbol": "a", "limit_times": 0, "change_pct": 1.0}) is None
