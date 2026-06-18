"""封单强度评分（limit_list_d：fd_amount / open_times / strth）。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _score_fd_amount(fd_amount: float) -> float:
    """Tushare fd_amount 单位为万元。"""
    if fd_amount <= 0:
        return 0.0
    if fd_amount >= 50_000:
        return 1.0
    if fd_amount >= 20_000:
        return 0.9
    if fd_amount >= 10_000:
        return 0.8
    if fd_amount >= 5_000:
        return 0.65
    if fd_amount >= 1_000:
        return 0.5
    return 0.35


def _score_open_times(open_times: int) -> float:
    if open_times <= 0:
        return 1.0
    if open_times == 1:
        return 0.75
    if open_times == 2:
        return 0.5
    return 0.25


def seal_strength_score(
    *,
    fd_amount: float | None = None,
    open_times: int | None = None,
    strth: float | None = None,
) -> float:
    """封单强度 0–1；优先 Tushare strth（0–100）。"""
    if strth is not None and strth > 0:
        return _clamp01(strth / 100.0)

    parts: list[float] = []
    if fd_amount is not None and fd_amount > 0:
        parts.append(_score_fd_amount(fd_amount))
    if open_times is not None:
        parts.append(_score_open_times(max(0, open_times)))
    if not parts:
        return 0.0
    return round(_clamp01(sum(parts) / len(parts)), 4)


def seal_strength_from_row(row: Mapping[str, Any]) -> float:
    """从行情行读取封单字段并评分。"""
    fd_raw = row.get("fd_amount")
    open_raw = row.get("open_times")
    strth_raw = row.get("strth")

    fd_amount: float | None = None
    open_times: int | None = None
    strth: float | None = None

    if fd_raw not in (None, ""):
        try:
            fd_amount = float(fd_raw)
        except (TypeError, ValueError):
            fd_amount = None
    if open_raw not in (None, ""):
        try:
            open_times = int(float(open_raw))
        except (TypeError, ValueError):
            open_times = None
    if strth_raw not in (None, ""):
        try:
            strth = float(strth_raw)
        except (TypeError, ValueError):
            strth = None

    preset = row.get("seal_strength_score")
    if preset not in (None, ""):
        try:
            return _clamp01(float(preset))
        except (TypeError, ValueError):
            pass

    return seal_strength_score(fd_amount=fd_amount, open_times=open_times, strth=strth)
