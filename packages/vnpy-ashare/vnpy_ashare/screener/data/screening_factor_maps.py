"""选股因子映射拉取（量比 / 换手 / 行业；无 ScreeningContext 类定义）。"""

from __future__ import annotations

from vnpy_ashare.data.download_concurrency import avg_turnover_prefetch_max_workers, run_parallel_map
from vnpy_ashare.domain.time.trade_dates import iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factors import (
    fetch_daily_basic,
    fetch_stock_industry_l1_map,
    fetch_stock_industry_map,
)
from vnpy_ashare.screener.data.screening_context_registry import get_screening_context


def fetch_volume_ratio_map_uncached() -> dict[str, float]:
    try:
        basic_rows, _ = fetch_daily_basic()
    except Exception:
        return {}
    return {
        str(row.get("vt_symbol") or ""): float(row.get("volume_ratio") or 0)
        for row in basic_rows
        if row.get("vt_symbol") and float(row.get("volume_ratio") or 0) > 0
    }


def get_volume_ratio_map() -> dict[str, float]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_volume_ratio_map()
    return fetch_volume_ratio_map_uncached()


def fetch_avg_turnover_map_uncached(*, lookback_days: int = 5) -> dict[str, float]:
    trade_dates = list(iter_trade_date_strs(max_lookback=lookback_days))

    def _fetch_day(trade_date: str) -> list[tuple[str, float]]:
        try:
            rows, _ = fetch_daily_basic(trade_date=trade_date)
        except Exception:
            return []
        day_rows: list[tuple[str, float]] = []
        for row in rows:
            vt_symbol = str(row.get("vt_symbol") or "")
            turnover = float(row.get("turnover_rate") or 0)
            if not vt_symbol or turnover <= 0:
                continue
            day_rows.append((vt_symbol, turnover))
        return day_rows

    workers = avg_turnover_prefetch_max_workers(item_count=len(trade_dates))
    day_results = run_parallel_map(trade_dates, _fetch_day, max_workers=workers)
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for day_rows in day_results:
        for vt_symbol, turnover in day_rows:
            sums[vt_symbol] = sums.get(vt_symbol, 0.0) + turnover
            counts[vt_symbol] = counts.get(vt_symbol, 0) + 1
    return {vt_symbol: sums[vt_symbol] / counts[vt_symbol] for vt_symbol in sums if counts.get(vt_symbol, 0) > 0}


def get_avg_turnover_map() -> dict[str, float]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_avg_turnover_map()
    return fetch_avg_turnover_map_uncached()


def get_stock_industry_map() -> dict[str, str]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_industry_map()
    try:
        return fetch_stock_industry_map()
    except Exception:
        return {}


def get_stock_industry_l1_map() -> dict[str, str]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_industry_l1_map()
    try:
        return fetch_stock_industry_l1_map()
    except Exception:
        return {}
