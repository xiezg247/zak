"""通用数值解析（领域层与存储层共用）。"""

from __future__ import annotations

from typing import Any


def float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def coerce_float(value: Any) -> float | None:
    """宽松数值解析（含字符串），用于 DB / API 原始字段。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
