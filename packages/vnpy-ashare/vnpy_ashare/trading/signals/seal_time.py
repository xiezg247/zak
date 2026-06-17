"""封板时间解析与评分（limit_list_d / 分 K 共用）。"""

from __future__ import annotations


def parse_clock_minutes(text: str) -> int | None:
    raw = str(text or "").strip().replace(":", "")
    if len(raw) < 4:
        return None
    try:
        hours = int(raw[:2])
        minutes = int(raw[2:4])
    except ValueError:
        return None
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        return None
    return hours * 60 + minutes


def seal_time_score(first_time: str) -> float:
    """封板时间得分；缺失时返回 0。"""
    minutes = parse_clock_minutes(first_time)
    if minutes is None:
        return 0.0
    if 565 <= minutes <= 630:
        return 1.0
    if 630 < minutes <= 810:
        return 0.7
    if 810 < minutes <= 900:
        return 0.5
    return 0.0


def format_seal_time_label(first_time: str) -> str:
    minutes = parse_clock_minutes(first_time)
    if minutes is None:
        return ""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d} 封板"


def seal_before_cutoff(first_time: str, *, cutoff_minutes: int = 630) -> bool:
    """是否早于 cutoff（默认 10:30）。"""
    minutes = parse_clock_minutes(first_time)
    if minutes is None:
        return True
    return minutes <= cutoff_minutes
