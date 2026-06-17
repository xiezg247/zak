"""分 K 首次触板时间（TickFlow）与 limit_list_d 回退。"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike

from strategies.ultra_short_signals import calc_limit_price
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import CHINA_TZ, is_ashare_trading_session
from vnpy_ashare.integrations.tickflow.klines import fetch_intraday_bars
from vnpy_ashare.integrations.tushare.limit_list_fallback import load_limit_list_first_time_map
from vnpy_ashare.trading.signals.seal_time import parse_clock_minutes, seal_time_score


class _MinuteBar(Protocol):
    datetime: datetime
    high_price: float


def infer_prev_close_from_row(row: QuoteRowLike | Mapping[str, Any]) -> float | None:
    """由现价与涨跌幅反推昨收。"""
    last_raw = row.get("last_price") if row.get("last_price") is not None else row.get("close")
    change_raw = row.get("change_pct")
    if last_raw is None or change_raw is None:
        return None
    try:
        last_price = float(last_raw)
        change_pct = float(change_raw)
    except (TypeError, ValueError):
        return None
    if last_price <= 0:
        return None
    denom = 1 + change_pct / 100
    if denom <= 0:
        return None
    return round(last_price / denom, 4)


def detect_seal_time_from_minute_bars(
    bars: list[_MinuteBar],
    *,
    limit_price: float,
    tolerance: float = 0.002,
) -> str:
    """从分 K 序列检测首次触及涨停价时刻，返回 HHMM 或 HHMMSS 风格字符串。"""
    if limit_price <= 0 or not bars:
        return ""
    threshold = limit_price * (1 - tolerance)
    ordered = sorted(bars, key=lambda item: item.datetime)
    for bar in ordered:
        if float(bar.high_price) >= threshold:
            local = bar.datetime
            if local.tzinfo is None:
                local = local.replace(tzinfo=CHINA_TZ)
            else:
                local = local.astimezone(CHINA_TZ)
            return f"{local.hour:02d}{local.minute:02d}{local.second:02d}"
    return ""


def fetch_intraday_seal_time(
    vt_symbol: str,
    *,
    prev_close: float,
) -> str:
    """拉 TickFlow 当日分 K，解析首次触板时间；失败返回空串。"""
    if prev_close <= 0:
        return ""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return ""
    limit_price = calc_limit_price(prev_close, symbol=item.symbol)
    if limit_price <= 0:
        return ""
    try:
        bars = fetch_intraday_bars(item, period="1m")
    except Exception:
        return ""
    return detect_seal_time_from_minute_bars(bars, limit_price=limit_price)


def resolve_first_time(
    vt_symbol: str,
    *,
    prev_close: float | None = None,
    limit_list_map: dict[str, str] | None = None,
    prefer_intraday: bool = False,
) -> str:
    """盘中优先 TickFlow 分 K；其余用 limit_list_d。"""
    fallback = ""
    if limit_list_map is not None:
        fallback = str(limit_list_map.get(vt_symbol) or "").strip()
    if prefer_intraday and is_ashare_trading_session() and prev_close is not None and prev_close > 0:
        intraday = fetch_intraday_seal_time(vt_symbol, prev_close=prev_close)
        if intraday:
            return intraday
    if fallback:
        return fallback
    if limit_list_map is None:
        return str(load_limit_list_first_time_map().get(vt_symbol) or "").strip()
    return ""


def build_first_time_map(
    rows: Sequence[QuoteRowLike | Mapping[str, Any]],
    *,
    max_intraday_fetch: int = 0,
) -> dict[str, str]:
    """合并 limit_list_d 与盘中 TickFlow 触板时间（仅补缺失项）。"""
    result = dict(load_limit_list_first_time_map())
    if not is_ashare_trading_session() or max_intraday_fetch <= 0:
        return result

    pending: list[tuple[str, float]] = []
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol or result.get(vt_symbol):
            continue
        prev_close = infer_prev_close_from_row(row)
        if prev_close is None or prev_close <= 0:
            continue
        pending.append((vt_symbol, prev_close))

    for vt_symbol, prev_close in pending[:max_intraday_fetch]:
        intraday = fetch_intraday_seal_time(vt_symbol, prev_close=prev_close)
        if intraday and parse_clock_minutes(intraday) is not None:
            result[vt_symbol] = intraday
    return result


def attach_first_time_fields(
    rows: Sequence[QuoteRow | MutableMapping[str, Any]],
    *,
    max_intraday_fetch: int = 0,
) -> None:
    """为行写入 first_time / seal_time_score（就地修改）。"""
    if not rows:
        return
    time_map = build_first_time_map(rows, max_intraday_fetch=max_intraday_fetch)
    for row in rows:
        vt = str(row.get("vt_symbol") or "")
        first_time = time_map.get(vt, "")
        if first_time:
            row["first_time"] = first_time
            row["seal_time_score"] = seal_time_score(first_time)
