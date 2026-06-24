"""个股主力净流入序列（优先本地 prefetch 缓存）。"""

from __future__ import annotations

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.time.trade_dates import iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factors import DATASET_MONEYFLOW, get_cached_rows
from vnpy_ashare.services.stock.context import fetch_stock_moneyflow_series

_MONEYFLOW_LOOKBACK_DAYS = 15


def load_stock_moneyflow_values(vt_symbol: str, *, days: int = _MONEYFLOW_LOOKBACK_DAYS) -> list[float]:
    """近 N 交易日主力净流入序列（万元，升序）。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return []

    lookback = max(5, min(int(days or _MONEYFLOW_LOOKBACK_DAYS), 60))
    trade_dates = list(iter_trade_date_strs(max_lookback=lookback))
    trade_dates.reverse()

    values: list[float] = []
    for trade_date in trade_dates:
        cached = get_cached_rows(DATASET_MONEYFLOW, trade_date)
        if not cached:
            continue
        row = next(
            (record for record in cached if record.get("ts_code") == item.ts_code or record.get("vt_symbol") == item.vt_symbol),
            None,
        )
        if row is None:
            values.append(0.0)
        else:
            values.append(float(row.get("net_mf_amount") or 0.0))

    if len(values) >= 10:
        return values[-lookback:]

    history = fetch_stock_moneyflow_series(item.ts_code, days=lookback)
    if not history:
        return values
    history.sort(key=lambda row: row.trade_date)
    return [float(row.net_mf_amount or 0.0) for row in history[-lookback:]]
