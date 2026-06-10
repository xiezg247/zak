"""配方结果硬过滤（ST、流动性）。"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_MIN_AMOUNT_YUAN = 30_000_000.0  # 3000 万元


def recipe_min_amount_yuan() -> float:
    raw = os.getenv("RECIPE_MIN_AMOUNT_YUAN", "").strip()
    if not raw:
        return DEFAULT_MIN_AMOUNT_YUAN
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_MIN_AMOUNT_YUAN


def recipe_exclude_st_enabled() -> bool:
    return os.getenv("RECIPE_EXCLUDE_ST", "1").strip().lower() not in ("0", "false", "no")


def is_st_stock(name: str) -> bool:
    text = (name or "").strip().upper()
    return "ST" in text


def row_amount_yuan(row: dict[str, Any]) -> float:
    amount = row.get("amount")
    if amount not in (None, ""):
        return float(amount or 0)
    # Tushare daily_basic 无 amount 时用 close * volume 粗估（volume 为手时需 ×100，此处仅作兜底）
    close = float(row.get("close") or row.get("last_price") or 0)
    volume = float(row.get("volume") or 0)
    if close > 0 and volume > 0:
        return close * volume * 100
    return 0.0


def apply_recipe_filters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """排除 ST 与低于成交额下限的标的。"""
    min_amount = recipe_min_amount_yuan()
    exclude_st = recipe_exclude_st_enabled()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "")
        if exclude_st and is_st_stock(name):
            continue
        if min_amount > 0 and row_amount_yuan(row) < min_amount:
            continue
        filtered.append(row)
    return filtered
