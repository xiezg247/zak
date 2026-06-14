"""维度混合评分测试。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.scoring import blended_score, metric_percentile, relative_ratio


def test_metric_percentile_higher_is_better() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert metric_percentile(4.0, values) == 100.0
    assert metric_percentile(1.0, values) == 25.0


def test_blended_score_between_rank_and_metric() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    score = blended_score(2, 4, 3.0, values, blend=0.5)
    assert 62.5 <= score <= 87.5


def test_relative_ratio_fallback_to_current() -> None:
    assert relative_ratio(5.0, 0.0) == 5.0
    assert relative_ratio(6.0, 3.0) == 2.0
