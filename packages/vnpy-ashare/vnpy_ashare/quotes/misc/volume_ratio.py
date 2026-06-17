"""盘中量比：TickFlow 成交量 + Tushare 近 N 日日均量。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.domain.time.market_hours import INTRADAY_SESSION_MINUTES, elapsed_trading_minutes
from vnpy_ashare.domain.time.trade_dates import iter_trade_date_strs
from vnpy_ashare.integrations.tushare.client import get_tushare_pro
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot

_AVG_VOLUME_CACHE: tuple[dict[str, float], float] | None = None
_AVG_VOLUME_TTL_SEC = 300.0
_DEFAULT_LOOKBACK_DAYS = 5


def compute_intraday_volume_ratio(
    volume_lots: float,
    avg_daily_volume_lots: float,
    *,
    dt: datetime | None = None,
) -> float:
    """量比 = 当日每分钟均量 / 近 N 日每分钟均量。"""
    if volume_lots <= 0 or avg_daily_volume_lots <= 0:
        return 0.0
    elapsed = elapsed_trading_minutes(dt)
    if elapsed <= 0:
        return 0.0
    today_per_min = volume_lots / elapsed
    base_per_min = avg_daily_volume_lots / float(INTRADAY_SESSION_MINUTES)
    if base_per_min <= 0:
        return 0.0
    ratio = today_per_min / base_per_min
    return round(ratio, 2) if ratio > 0 else 0.0


def load_avg_daily_volume_map_by_tickflow(
    *,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    force_refresh: bool = False,
) -> dict[str, float]:
    """近 N 个交易日日均成交量（手），按 TickFlow symbol 索引（不含当日）。"""
    global _AVG_VOLUME_CACHE
    now = time.monotonic()
    if not force_refresh and _AVG_VOLUME_CACHE is not None:
        volume_map, cached_at = _AVG_VOLUME_CACHE
        if now - cached_at < _AVG_VOLUME_TTL_SEC:
            return volume_map
    try:
        volume_map = _fetch_avg_daily_volume_map_by_tickflow(lookback_days=lookback_days)
    except Exception:
        volume_map = {}
    _AVG_VOLUME_CACHE = (volume_map, now)
    return volume_map


def _fetch_avg_daily_volume_map_by_tickflow(*, lookback_days: int) -> dict[str, float]:

    pro = get_tushare_pro()
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    yesterday = last_trading_day(on_or_before=last_trading_day() - timedelta(days=1))
    for trade_date in iter_trade_date_strs(max_lookback=lookback_days, start=yesterday):
        frame = pro.daily(trade_date=trade_date, fields="ts_code,vol")
        if frame is None or frame.empty:
            continue
        for record in frame.to_dict(orient="records"):
            ts_code = str(record.get("ts_code") or "").strip()
            vol = float(record.get("vol") or 0)
            if not ts_code or vol <= 0:
                continue
            item = parse_stock_symbol(ts_code)
            if item is None:
                continue
            tf_symbol = item.tickflow_symbol
            sums[tf_symbol] = sums.get(tf_symbol, 0.0) + vol
            counts[tf_symbol] = counts.get(tf_symbol, 0) + 1
    return {tf_symbol: sums[tf_symbol] / counts[tf_symbol] for tf_symbol in sums if counts.get(tf_symbol, 0) > 0}


def fill_intraday_volume_ratios(
    quotes: dict[str, QuoteSnapshot],
    *,
    dt: datetime | None = None,
) -> None:
    """Tushare daily_basic 缺量比时，用实时成交量推算盘中量比。"""
    if not quotes:
        return
    if elapsed_trading_minutes(dt) <= 0:
        return
    needs = [tf_symbol for tf_symbol, quote in quotes.items() if quote.volume_ratio <= 0 and quote.volume > 0]
    if not needs:
        return
    avg_map = load_avg_daily_volume_map_by_tickflow()
    if not avg_map:
        return
    for tf_symbol in needs:
        quote = quotes[tf_symbol]
        avg_vol = avg_map.get(tf_symbol)
        if avg_vol is None or avg_vol <= 0:
            continue
        ratio = compute_intraday_volume_ratio(quote.volume, avg_vol, dt=dt)
        if ratio > 0:
            quote.volume_ratio = ratio
