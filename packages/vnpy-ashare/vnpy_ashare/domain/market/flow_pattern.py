"""资金流/指标序列形态分类（板块与个股共用）。"""

from __future__ import annotations

from collections.abc import Sequence


def classify_flow_pattern_values(values: Sequence[float]) -> str:
    """按近 N 日数值序列归类为五种流动方向标签。"""
    if not values:
        return "—"
    seq = list(values)
    positive_days = sum(1 for value in seq if value > 0)
    cumulative = sum(seq)
    first_7 = sum(seq[:7])
    second_8 = sum(seq[7:])
    last_5 = sum(seq[-5:])
    first_10 = sum(seq[:10]) if len(seq) >= 10 else sum(seq[:-5]) if len(seq) > 5 else 0.0

    if positive_days >= 10 and (last_5 - first_10) > 0:
        return "持续流入"
    if positive_days <= 5 and cumulative < 0:
        return "持续流出"
    if first_7 < 0 and second_8 > 0:
        return "先出后入"
    if first_7 > 0 and second_8 < 0:
        return "先入后出"
    return "震荡"
