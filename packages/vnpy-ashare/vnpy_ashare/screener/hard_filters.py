"""选股硬过滤（ST、流动性 / 小市值）。

配方、策略 preset、形态选股共用；QSettings 用户偏好与环境变量 ``RECIPE_*`` 均可生效（环境变量优先）。
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_MIN_AMOUNT_YUAN = 30_000_000.0  # 3000 万元
# Tushare daily_basic.total_mv 单位为万元；50 亿 = 500000 万元
DEFAULT_MIN_TOTAL_MV_WAN = 500_000.0


def recipe_min_amount_yuan() -> float:
    raw = os.getenv("RECIPE_MIN_AMOUNT_YUAN", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return DEFAULT_MIN_AMOUNT_YUAN
    from vnpy_ashare.screener.hard_filter_prefs import load_hard_filter_prefs

    return load_hard_filter_prefs().min_amount_yuan


def recipe_exclude_st_enabled() -> bool:
    raw = os.getenv("RECIPE_EXCLUDE_ST", "").strip()
    if raw:
        return raw.lower() not in ("0", "false", "no")
    from vnpy_ashare.screener.hard_filter_prefs import load_hard_filter_prefs

    return load_hard_filter_prefs().exclude_st


def recipe_min_total_mv_wan() -> float:
    raw = os.getenv("RECIPE_MIN_TOTAL_MV_WAN", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return DEFAULT_MIN_TOTAL_MV_WAN
    from vnpy_ashare.screener.hard_filter_prefs import load_hard_filter_prefs

    return load_hard_filter_prefs().min_total_mv_wan


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


def passes_liquidity_filter(row: dict[str, Any]) -> bool:
    """成交额或总市值（小资金）达标；无相关字段时不排除。"""
    min_amount = recipe_min_amount_yuan()
    min_mv = recipe_min_total_mv_wan()

    amount_raw = row.get("amount")
    if amount_raw not in (None, ""):
        if min_amount <= 0:
            return True
        return float(amount_raw or 0) >= min_amount

    total_mv = float(row.get("total_mv") or row.get("circ_mv") or 0)
    if total_mv > 0:
        if min_mv <= 0:
            return True
        return total_mv >= min_mv

    estimated = row_amount_yuan(row)
    if estimated > 0 and min_amount > 0:
        return estimated >= min_amount

    return True


def passes_screening_hard_filter(row: dict[str, Any]) -> bool:
    name = str(row.get("name") or "")
    if recipe_exclude_st_enabled() and is_st_stock(name):
        return False
    return passes_liquidity_filter(row)


def apply_recipe_filters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """排除 ST 与流动性 / 小市值不达标的标的。"""
    return [row for row in rows if passes_screening_hard_filter(row)]


# 策略选股等路径别名
apply_screening_filters = apply_recipe_filters
