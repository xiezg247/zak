"""数值解析（外部 API 字段标准化）。"""

from __future__ import annotations

from typing import Any


def safe_float(value: Any, *, default: float = 0.0) -> float:
    """将 Tushare / TickFlow 等 API 字段安全转为 float。"""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
