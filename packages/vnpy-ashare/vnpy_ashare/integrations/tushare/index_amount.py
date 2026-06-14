"""指数历史成交额（Tushare index_daily）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.domain.index_amount import IndexAmountPoint, IndexAmountSeries
from vnpy_ashare.domain.numbers import safe_float
from vnpy_ashare.integrations.tushare.cache import DATASET_INDEX_DAILY, get_cached_rows, set_cached_rows
from vnpy_ashare.integrations.tushare.client import get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import _latest_trade_date_str

DEFAULT_TRADING_DAYS = 30
_INDEX_AMOUNT_CALENDAR_BUFFER = 50
_MEMORY_CACHE: dict[tuple[str, int], IndexAmountSeries] = {}


def index_daily_amount_to_yi(amount: float) -> float:
    """Tushare index_daily.amount 单位为千元 → 亿元。"""
    if amount <= 0:
        return 0.0
    return amount * 1000.0 / 1e8


def _rows_to_points(rows: list[dict[str, Any]], *, trading_days: int) -> list[IndexAmountPoint]:
    filtered = [row for row in rows if str(row.get("trade_date") or "").strip()]
    filtered.sort(key=lambda row: str(row["trade_date"]))
    tail = filtered[-trading_days:]
    points: list[IndexAmountPoint] = []
    for row in tail:
        amount = safe_float(row.get("amount"))
        if amount <= 0:
            continue
        points.append(
            IndexAmountPoint(
                trade_date=str(row["trade_date"]),
                amount_yi=round(index_daily_amount_to_yi(amount), 2),
            )
        )
    return points


def _filter_cached_rows(ts_code: str, cached_rows: list[dict[str, Any]], *, trading_days: int) -> list[dict[str, Any]]:
    matched = [row for row in cached_rows if str(row.get("ts_code") or "") == ts_code]
    if len(matched) < max(trading_days // 2, 5):
        return []
    return matched


def _fetch_index_rows(ts_code: str, *, trade_date: str, calendar_days: int) -> list[dict[str, Any]]:
    end_dt = datetime.strptime(trade_date, "%Y%m%d")
    start_date = (end_dt - timedelta(days=calendar_days)).strftime("%Y%m%d")
    pro = get_tushare_pro()
    frame = pro.index_daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=trade_date,
        fields="ts_code,trade_date,amount",
    )
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            {
                "ts_code": str(record.get("ts_code", ts_code)),
                "trade_date": str(record.get("trade_date", "")),
                "amount": safe_float(record.get("amount")),
            }
        )
    return rows


def _merge_index_daily_cache(trade_date: str, fresh_rows: list[dict[str, Any]]) -> None:
    if not fresh_rows:
        return
    cached = list(get_cached_rows(DATASET_INDEX_DAILY, trade_date) or [])
    by_key = {(str(row.get("ts_code") or ""), str(row.get("trade_date") or "")): row for row in cached}
    for row in fresh_rows:
        key = (str(row.get("ts_code") or ""), str(row.get("trade_date") or ""))
        if key[0] and key[1]:
            by_key[key] = row
    merged = sorted(by_key.values(), key=lambda row: (str(row.get("ts_code") or ""), str(row.get("trade_date") or "")))
    set_cached_rows(DATASET_INDEX_DAILY, trade_date, merged)


def fetch_index_amount_history(
    ts_code: str,
    *,
    label: str = "",
    trading_days: int = DEFAULT_TRADING_DAYS,
    use_memory_cache: bool = True,
) -> IndexAmountSeries:
    """拉取单指数近 N 个交易日成交额（亿元）。"""
    cache_key = (ts_code, trading_days)
    if use_memory_cache and cache_key in _MEMORY_CACHE:
        cached = _MEMORY_CACHE[cache_key]
        if not cached.error:
            return cached

    trade_date = _latest_trade_date_str()
    try:
        cached_rows = get_cached_rows(DATASET_INDEX_DAILY, trade_date) or []
        matched = _filter_cached_rows(ts_code, cached_rows, trading_days=trading_days)
        if not matched:
            fetched = _fetch_index_rows(
                ts_code,
                trade_date=trade_date,
                calendar_days=max(_INDEX_AMOUNT_CALENDAR_BUFFER, trading_days * 2),
            )
            if fetched:
                _merge_index_daily_cache(trade_date, fetched)
                matched = fetched
        points = _rows_to_points(matched, trading_days=trading_days)
        if not points:
            series = IndexAmountSeries(
                ts_code=ts_code,
                label=label or ts_code,
                points=(),
                error="暂无历史成交额（需 TUSHARE_TOKEN，或该指数暂无 index_daily 数据）",
            )
        else:
            series = IndexAmountSeries(ts_code=ts_code, label=label or ts_code, points=tuple(points))
    except Exception as ex:
        series = IndexAmountSeries(
            ts_code=ts_code,
            label=label or ts_code,
            points=(),
            error=str(ex),
        )

    if use_memory_cache and not series.error:
        _MEMORY_CACHE[cache_key] = series
    return series


def clear_index_amount_memory_cache() -> None:
    _MEMORY_CACHE.clear()
