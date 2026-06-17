"""数值解析与 coercion（DB / API 字段标准化）。"""

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


def safe_float(value: Any, *, default: float = 0.0) -> float:
    """将 Tushare / TickFlow 等 API 字段安全转为 float。"""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
