"""Tushare Pro 历史 K 线拉取并写入本地数据库（日 K / 分 K）。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData

from vnpy_ashare.data.bar_store import invalidate_bar_overview_cache
from vnpy_ashare.data.minute_periods import normalize_period
from vnpy_ashare.domain.symbols.stock import symbol_exchange_to_ts_code
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.rate_limit import acquire_tushare, is_rate_limited, rate_limit_retry_delay

_CHINA_TZ = ZoneInfo("Asia/Shanghai")
_MINUTE_CHUNK_DAYS = 20
_MINUTE_CHUNK_DELAY_SEC = 0.15
_DAILY_API = "daily"
_STK_MINS_API = "stk_mins"
_MAX_RATE_LIMIT_RETRIES = 3

_PERIOD_TO_TUSHARE_FREQ: dict[str, str] = {
    "1m": "1min",
}


def _period_to_freq(period: str) -> str:
    normalized = normalize_period(period)
    freq = _PERIOD_TO_TUSHARE_FREQ.get(normalized)
    if freq is None:
        raise ValueError(f"Tushare 不支持的分 K 周期: {period}")
    return freq


def _format_trade_date(value: datetime) -> str:
    return value.strftime("%Y%m%d")


def _format_datetime_ts(value: datetime) -> str:
    local = value.astimezone(_CHINA_TZ) if value.tzinfo else value.replace(tzinfo=_CHINA_TZ)
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _parse_trade_date(text: str) -> datetime:
    raw = str(text or "").strip()
    if len(raw) == 8 and raw.isdigit():
        dt = datetime.strptime(raw, "%Y%m%d")
    elif len(raw) >= 10:
        if " " in raw:
            dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
    else:
        raise ValueError(f"无法解析 trade_date: {text}")
    return dt.replace(tzinfo=_CHINA_TZ)


def _parse_trade_time(text: str) -> datetime:
    raw = str(text or "").strip()
    if " " in raw:
        dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
    elif len(raw) == 8 and raw.isdigit():
        dt = datetime.strptime(raw, "%Y%m%d")
    else:
        dt = datetime.strptime(raw[:10], "%Y-%m-%d")
    return dt.replace(tzinfo=_CHINA_TZ)


def _iter_minute_chunks(start: datetime, end: datetime, *, chunk_days: int = _MINUTE_CHUNK_DAYS):
    if start > end:
        return
    cursor = start
    step = timedelta(days=max(1, int(chunk_days)))
    while cursor <= end:
        chunk_end = min(end, cursor + step - timedelta(seconds=1))
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(seconds=1)


def daily_frame_to_bars(
    frame: pd.DataFrame,
    *,
    symbol: str,
    exchange: Exchange,
) -> list[BarData]:
    """Tushare daily 表 → VeighNa BarData（vol 为手，amount 千元）。"""
    if frame is None or frame.empty:
        return []

    bars: list[BarData] = []
    for record in frame.to_dict(orient="records"):
        trade_date = record.get("trade_date")
        if trade_date is None or pd.isna(trade_date):
            continue
        open_price = record.get("open")
        if open_price is None or pd.isna(open_price):
            continue

        vol = record.get("vol", 0)
        amount = record.get("amount", 0)
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=_parse_trade_date(str(trade_date)),
                interval=Interval.DAILY,
                open_price=float(open_price),
                high_price=float(record.get("high") or open_price),
                low_price=float(record.get("low") or open_price),
                close_price=float(record.get("close") or open_price),
                volume=float(vol or 0),
                turnover=float(amount or 0) * 1000.0,
                open_interest=0,
                gateway_name="TS",
            )
        )
    bars.sort(key=lambda item: item.datetime)
    return bars


def minute_frame_to_bars(
    frame: pd.DataFrame,
    *,
    symbol: str,
    exchange: Exchange,
) -> list[BarData]:
    """Tushare stk_mins 表 → VeighNa BarData（vol 为股，amount 为元）。"""
    if frame is None or frame.empty:
        return []

    bars: list[BarData] = []
    for record in frame.to_dict(orient="records"):
        trade_time = record.get("trade_time")
        if trade_time is None or pd.isna(trade_time):
            continue
        open_price = record.get("open")
        if open_price is None or pd.isna(open_price):
            continue

        vol = record.get("vol", 0)
        amount = record.get("amount", 0)
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=_parse_trade_time(str(trade_time)),
                interval=Interval.MINUTE,
                open_price=float(open_price),
                high_price=float(record.get("high") or open_price),
                low_price=float(record.get("low") or open_price),
                close_price=float(record.get("close") or open_price),
                volume=float(vol or 0),
                turnover=float(amount or 0),
                open_interest=0,
                gateway_name="TS",
            )
        )
    bars.sort(key=lambda item: item.datetime)
    return bars


def _call_tushare(api_name: str, func):
    """带全局限流与限流退避重试的 Tushare 调用。"""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        acquire_tushare(api_name)
        try:
            return func()
        except Exception as ex:
            last_exc = ex
            if is_rate_limited(ex) and attempt + 1 < _MAX_RATE_LIMIT_RETRIES:
                time.sleep(rate_limit_retry_delay(attempt))
                continue
            raise
    assert last_exc is not None
    raise last_exc


def fetch_daily_bars(
    symbol: str,
    exchange: Exchange,
    *,
    start: datetime,
    end: datetime,
) -> list[BarData]:
    """从 Tushare Pro 拉取单票日 K。"""
    ts_code = symbol_exchange_to_ts_code(symbol, exchange)
    pro = get_tushare_pro()

    def _fetch():
        return pro.daily(
            ts_code=ts_code,
            start_date=_format_trade_date(start),
            end_date=_format_trade_date(end),
            fields="ts_code,trade_date,open,high,low,close,vol,amount",
        )

    frame = _call_tushare(_DAILY_API, _fetch)
    return daily_frame_to_bars(frame, symbol=symbol, exchange=exchange)


def fetch_minute_bars(
    symbol: str,
    exchange: Exchange,
    *,
    start: datetime,
    end: datetime,
    period: str = "1m",
    chunk_delay: float = _MINUTE_CHUNK_DELAY_SEC,
) -> list[BarData]:
    """从 Tushare Pro 拉取单票历史分 K（按日期分段，避免单次超量）。"""
    ts_code = symbol_exchange_to_ts_code(symbol, exchange)
    freq = _period_to_freq(period)
    pro = get_tushare_pro()
    merged: dict[datetime, BarData] = {}
    chunks = list(_iter_minute_chunks(start, end))
    for index, (chunk_start, chunk_end) in enumerate(chunks):
        chunk_start_ts = _format_datetime_ts(chunk_start)
        chunk_end_ts = _format_datetime_ts(chunk_end)

        def _fetch(start_ts=chunk_start_ts, end_ts=chunk_end_ts):
            return pro.stk_mins(
                ts_code=ts_code,
                freq=freq,
                start_date=start_ts,
                end_date=end_ts,
            )

        frame = _call_tushare(_STK_MINS_API, _fetch)
        for bar in minute_frame_to_bars(frame, symbol=symbol, exchange=exchange):
            merged[bar.datetime] = bar
        if chunk_delay > 0 and index + 1 < len(chunks):
            time.sleep(chunk_delay)
    return sorted(merged.values(), key=lambda item: item.datetime)


def _save_bars(bars: list[BarData]) -> int:
    database = get_database()
    database.save_bar_data(bars)
    invalidate_bar_overview_cache()
    return len(bars)


def download_daily_bars_tushare(
    symbol: str,
    exchange: Exchange,
    *,
    start: datetime,
    end: datetime,
) -> int:
    """下载日 K 并写入本地数据库，返回保存条数。"""
    bars = fetch_daily_bars(symbol, exchange, start=start, end=end)
    if not bars:
        raise RuntimeError(f"未获取到数据: {symbol}.{exchange.value}")
    return _save_bars(bars)


def download_minute_bars_tushare(
    symbol: str,
    exchange: Exchange,
    *,
    start: datetime,
    end: datetime,
    period: str = "1m",
) -> int:
    """下载历史分 K 并写入本地数据库，返回保存条数。"""
    bars = fetch_minute_bars(symbol, exchange, start=start, end=end, period=period)
    if not bars:
        raise RuntimeError(f"未获取到 {period} 数据: {symbol}.{exchange.value}")
    return _save_bars(bars)


__all__ = [
    "TushareNotConfiguredError",
    "daily_frame_to_bars",
    "download_daily_bars_tushare",
    "download_minute_bars_tushare",
    "fetch_daily_bars",
    "fetch_minute_bars",
    "minute_frame_to_bars",
]
