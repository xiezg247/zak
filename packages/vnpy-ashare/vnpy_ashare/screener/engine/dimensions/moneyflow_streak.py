"""批量计算主力净流入连涨天数（读 Tushare 本地缓存）。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare.factors import DATASET_MONEYFLOW, get_cached_rows
from vnpy_ashare.screener.data.data_source import iter_trade_date_strs


def build_positive_moneyflow_streak_map(
    vt_symbols: set[str] | frozenset[str],
    *,
    max_days: int = 5,
) -> dict[str, int]:
    """按交易日倒序批量统计连续净流入天数。"""
    symbols = {str(vt).strip() for vt in vt_symbols if str(vt).strip()}
    if not symbols:
        return {}

    daily_maps: list[dict[str, float]] = []
    for trade_date in iter_trade_date_strs(max_lookback=max_days):
        cached = get_cached_rows(DATASET_MONEYFLOW, trade_date)
        if cached is None:
            break
        day_map: dict[str, float] = {}
        for item in cached:
            vt = str(item.get("vt_symbol") or "").strip()
            if vt in symbols:
                day_map[vt] = float(item.get("net_mf_amount") or 0)
        daily_maps.append(day_map)

    result: dict[str, int] = {}
    for vt in symbols:
        streak = 0
        for day_map in daily_maps:
            if vt not in day_map:
                break
            if day_map[vt] > 0:
                streak += 1
            else:
                break
        if streak:
            result[vt] = streak
    return result
