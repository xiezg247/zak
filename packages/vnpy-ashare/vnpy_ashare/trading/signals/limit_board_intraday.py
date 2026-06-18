"""分 K 打板评估（TickFlow / 本地 1m 序列）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from strategies.ultra_short_signals import calc_limit_price
from vnpy_ashare.data.bar_store import load_period_bars, load_scope_bars
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.intraday_seal_time import detect_seal_time_from_minute_bars
from vnpy_ashare.trading.signals.seal_reopen import (
    SealReopenKind,
    detect_seal_reopen_from_minute_bars,
    format_seal_reopen_label,
    seal_reopen_score,
)
from vnpy_ashare.trading.signals.seal_time import parse_clock_minutes, seal_time_score

SessionPhase = Literal["partial", "closed"]


@dataclass(frozen=True)
class LimitBoardIntradaySnapshot:
    eligible: bool
    entry_price: float
    first_time: str
    one_word: bool
    seal_reopen_kind: SealReopenKind
    seal_reopen_label: str
    seal_reopen_score: float
    seal_time_score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class _MinuteBarLike:
    datetime: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float


def _session_minute_bars(bars: list[_MinuteBarLike]) -> list[_MinuteBarLike]:
    ordered = sorted(bars, key=lambda item: item.datetime)
    result: list[_MinuteBarLike] = []
    for bar in ordered:
        local = bar.datetime
        if local.tzinfo is None:
            local = local.replace(tzinfo=CHINA_TZ)
        else:
            local = local.astimezone(CHINA_TZ)
        if time(9, 30) <= local.time() <= time(15, 0):
            result.append(bar)
    return result


def _detect_one_word(
    bars: list[_MinuteBarLike],
    *,
    limit_price: float,
    max_amplitude: float,
) -> bool:
    if limit_price <= 0 or not bars:
        return False
    threshold = limit_price * 0.998
    day_high = max(float(bar.high_price) for bar in bars)
    day_low = min(float(bar.low_price) for bar in bars)
    if day_high < threshold:
        return False
    amplitude = (day_high - day_low) / limit_price * 100
    return amplitude >= 0 and amplitude < max_amplitude


def evaluate_limit_board_intraday(
    bars: list[_MinuteBarLike],
    *,
    prev_close: float,
    symbol: str,
    reject_one_word: bool = True,
    one_word_amplitude_max: float = 0.5,
    cutoff_minutes: int = 630,
    reject_broken: bool = True,
    reject_weak: bool = False,
    tolerance: float = 0.002,
    phase: SessionPhase = "closed",
) -> LimitBoardIntradaySnapshot:
    """基于分 K 序列评估打板条件；phase=partial 时仅用到当前 bar 为止。"""
    limit_price = calc_limit_price(prev_close, symbol=symbol)
    session_bars = _session_minute_bars(bars)
    reasons: list[str] = []
    warnings: list[str] = []

    if limit_price <= 0 or prev_close <= 0:
        return LimitBoardIntradaySnapshot(
            eligible=False,
            entry_price=0.0,
            first_time="",
            one_word=False,
            seal_reopen_kind="unknown",
            seal_reopen_label="",
            seal_reopen_score=0.0,
            seal_time_score=0.0,
            reasons=("昨收无效",),
            warnings=tuple(warnings),
        )

    if not session_bars:
        return LimitBoardIntradaySnapshot(
            eligible=False,
            entry_price=0.0,
            first_time="",
            one_word=False,
            seal_reopen_kind="unknown",
            seal_reopen_label="",
            seal_reopen_score=0.0,
            seal_time_score=0.0,
            reasons=("无有效分 K",),
            warnings=tuple(warnings),
        )

    first_time = detect_seal_time_from_minute_bars(session_bars, limit_price=limit_price, tolerance=tolerance)
    one_word = _detect_one_word(
        session_bars,
        limit_price=limit_price,
        max_amplitude=one_word_amplitude_max,
    )

    reopen_kind, break_count = detect_seal_reopen_from_minute_bars(
        session_bars,
        limit_price=limit_price,
        tolerance=tolerance,
    )
    if phase == "partial" and first_time and reopen_kind == "unknown":
        reopen_kind = "solid" if break_count <= 0 else "resealed" if break_count == 1 else "weak"

    reopen_label = format_seal_reopen_label(reopen_kind, open_times=break_count if break_count > 0 else None)
    reopen_score = seal_reopen_score(reopen_kind)
    time_score = seal_time_score(first_time)

    if not first_time:
        reasons.append("未触及涨停价")
    else:
        reasons.append(f"首次触板 {first_time[:4]}:{first_time[4:6]}")
        if reopen_label:
            reasons.append(reopen_label)

    eligible = bool(first_time)
    if eligible and reject_one_word and one_word:
        eligible = False
        reasons.append("近似一字板，打板回避")
    if eligible:
        touch_minutes = parse_clock_minutes(first_time)
        if touch_minutes is not None and touch_minutes > cutoff_minutes:
            eligible = False
            reasons.append(f"触板晚于 {cutoff_minutes // 60:02d}:{cutoff_minutes % 60:02d}")
    if eligible and phase == "closed":
        if reject_broken and reopen_kind == "broken":
            eligible = False
            reasons.append("炸板未回封")
        if reject_weak and reopen_kind == "weak":
            eligible = False
            reasons.append("多次打开，质量偏弱")

    if eligible:
        warnings.append("分 K 规则（TickFlow / 本地 1m）")
    elif phase == "partial":
        warnings.append("分 K 盘中评估（未收盘，炸板状态未最终确认）")

    return LimitBoardIntradaySnapshot(
        eligible=eligible,
        entry_price=limit_price if eligible else 0.0,
        first_time=first_time,
        one_word=one_word,
        seal_reopen_kind=reopen_kind,
        seal_reopen_label=reopen_label,
        seal_reopen_score=reopen_score,
        seal_time_score=time_score,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


_MINUTE_BARS_CACHE: dict[tuple[str, date], list] = {}


def clear_local_minute_bars_cache() -> None:
    """测试或换日时清空进程内分 K 缓存。"""
    _MINUTE_BARS_CACHE.clear()


def load_local_minute_bars_for_date(vt_symbol: str, trade_date: date) -> list:
    """读取本地库指定交易日的 1 分 K；无数据返回空列表。"""
    cache_key = (str(vt_symbol or "").strip(), trade_date)
    if cache_key in _MINUTE_BARS_CACHE:
        return _MINUTE_BARS_CACHE[cache_key]
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return []
    start = datetime.combine(trade_date, time(9, 0), tzinfo=CHINA_TZ)
    end = datetime.combine(trade_date, time(15, 30), tzinfo=CHINA_TZ)
    bars = load_period_bars(item.symbol, item.exchange, "1m", start, end)
    _MINUTE_BARS_CACHE[cache_key] = bars
    return bars


def resolve_prev_close_for_date(vt_symbol: str, trade_date: date) -> float:
    """取 trade_date 前一交易日收盘价（本地日 K）。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return 0.0
    start = datetime.combine(trade_date - timedelta(days=20), time(0, 0), tzinfo=CHINA_TZ)
    end = datetime.combine(trade_date, time(0, 0), tzinfo=CHINA_TZ)
    daily = load_scope_bars(item.symbol, item.exchange, "daily", start, end)
    if len(daily) < 1:
        return 0.0
    return float(daily[-1].close_price)


def evaluate_limit_board_from_local_minutes(
    vt_symbol: str,
    trade_date: date,
    *,
    reject_one_word: bool = True,
    one_word_amplitude_max: float = 0.5,
    cutoff_minutes: int = 630,
) -> LimitBoardIntradaySnapshot | None:
    """本地 1m + 日 K 昨收评估；无分 K 数据时返回 None。"""
    bars = load_local_minute_bars_for_date(vt_symbol, trade_date)
    if not bars:
        return None
    symbol = vt_symbol.split(".", 1)[0]
    prev_close = resolve_prev_close_for_date(vt_symbol, trade_date)
    if prev_close <= 0:
        return None
    return evaluate_limit_board_intraday(
        bars,
        prev_close=prev_close,
        symbol=symbol,
        reject_one_word=reject_one_word,
        one_word_amplitude_max=one_word_amplitude_max,
        cutoff_minutes=cutoff_minutes,
        phase="closed",
    )
