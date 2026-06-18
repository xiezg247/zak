"""分 K 半路评估（9:40–10:30 窗口 + 涨幅带 + 突破 + 放量）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.signals.limit_board_intraday import (
    load_local_minute_bars_for_date,
    resolve_prev_close_for_date,
)
from vnpy_ashare.trading.signals.seal_time import parse_clock_minutes

SessionPhase = Literal["partial", "closed"]

DEFAULT_WINDOW_START_MINUTES = 580  # 09:40
DEFAULT_WINDOW_END_MINUTES = 630  # 10:30


@dataclass(frozen=True)
class IntradayBreakoutSnapshot:
    eligible: bool
    entry_price: float
    trigger_time: str
    change_pct: float
    volume_ratio: float | None
    breakout_level: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class _MinuteBarLike:
    datetime: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


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


def _bar_clock_minutes(bar: _MinuteBarLike) -> int | None:
    local = bar.datetime
    if local.tzinfo is None:
        local = local.replace(tzinfo=CHINA_TZ)
    else:
        local = local.astimezone(CHINA_TZ)
    return local.hour * 60 + local.minute


def _format_trigger_time(bar: _MinuteBarLike) -> str:
    local = bar.datetime
    if local.tzinfo is None:
        local = local.replace(tzinfo=CHINA_TZ)
    else:
        local = local.astimezone(CHINA_TZ)
    return f"{local.hour:02d}{local.minute:02d}{local.second:02d}"


def _minute_volume_ratio(bars: list[_MinuteBarLike], index: int, *, recent: int = 5, base: int = 10) -> float | None:
    if index < base + recent - 1:
        return None
    recent_slice = bars[index - recent + 1 : index + 1]
    base_slice = bars[index - base - recent + 1 : index - recent + 1]
    if not recent_slice or not base_slice:
        return None
    recent_avg = sum(float(bar.volume) for bar in recent_slice) / len(recent_slice)
    base_avg = sum(float(bar.volume) for bar in base_slice) / len(base_slice)
    if base_avg <= 0:
        return None
    return recent_avg / base_avg


def _morning_high(bars: list[_MinuteBarLike], index: int) -> float:
    if index <= 0:
        return 0.0
    return max(float(bar.high_price) for bar in bars[:index])


def _bar_change_pct(bar: _MinuteBarLike, *, prev_close: float) -> float:
    if prev_close <= 0:
        return 0.0
    return (float(bar.close_price) - prev_close) / prev_close * 100


def _bar_in_window(
    bar: _MinuteBarLike,
    *,
    window_start_minutes: int,
    window_end_minutes: int,
) -> bool:
    minutes = _bar_clock_minutes(bar)
    if minutes is None:
        return False
    return window_start_minutes <= minutes <= window_end_minutes


def _evaluate_bar(
    bars: list[_MinuteBarLike],
    index: int,
    *,
    prev_close: float,
    symbol: str,
    min_change_pct: float,
    max_change_pct: float,
    volume_ratio_min: float,
    window_start_minutes: int,
    window_end_minutes: int,
) -> IntradayBreakoutSnapshot | None:
    bar = bars[index]
    if not _bar_in_window(
        bar,
        window_start_minutes=window_start_minutes,
        window_end_minutes=window_end_minutes,
    ):
        return None

    change_pct = _bar_change_pct(bar, prev_close=prev_close)
    row = {"symbol": symbol, "change_pct": change_pct}
    if is_at_limit_board(row):
        return None
    if not (min_change_pct <= change_pct <= max_change_pct):
        return None

    breakout_level = _morning_high(bars, index)
    if breakout_level <= 0 or float(bar.close_price) <= breakout_level:
        return None

    vol_ratio = _minute_volume_ratio(bars, index)
    if vol_ratio is not None and vol_ratio < volume_ratio_min:
        return None

    trigger_time = _format_trigger_time(bar)
    reasons = [
        f"涨幅 {change_pct:.1f}%（半路 {min_change_pct:.0f}–{max_change_pct:.0f}%）",
        f"突破日内前高 {breakout_level:.2f}",
    ]
    if vol_ratio is not None:
        reasons.append(f"分 K 量比 {vol_ratio:.1f}")
    if trigger_time and parse_clock_minutes(trigger_time) is not None:
        reasons.append(f"触发 {trigger_time[:2]}:{trigger_time[2:4]}")

    return IntradayBreakoutSnapshot(
        eligible=True,
        entry_price=float(bar.close_price),
        trigger_time=trigger_time,
        change_pct=change_pct,
        volume_ratio=vol_ratio,
        breakout_level=breakout_level,
        reasons=tuple(reasons),
        warnings=("分 K 规则（9:40–10:30 窗口）",),
    )


def evaluate_intraday_breakout_intraday(
    bars: list[_MinuteBarLike],
    *,
    prev_close: float,
    symbol: str,
    min_change_pct: float = 3.0,
    max_change_pct: float = 7.0,
    volume_ratio_min: float = 1.2,
    window_start_minutes: int = DEFAULT_WINDOW_START_MINUTES,
    window_end_minutes: int = DEFAULT_WINDOW_END_MINUTES,
    phase: SessionPhase = "closed",
) -> IntradayBreakoutSnapshot:
    """分 K 半路评估；partial 时只判定截至最后一根 bar。"""
    session_bars = _session_minute_bars(bars)
    empty = IntradayBreakoutSnapshot(
        eligible=False,
        entry_price=0.0,
        trigger_time="",
        change_pct=0.0,
        volume_ratio=None,
        breakout_level=0.0,
        reasons=("未满足半路条件",),
        warnings=("分 K 规则（9:40–10:30 窗口）",) if session_bars else ("无有效分 K",),
    )

    if prev_close <= 0 or not session_bars:
        return empty

    for index in range(len(session_bars)):
        hit = _evaluate_bar(
            session_bars,
            index,
            prev_close=prev_close,
            symbol=symbol,
            min_change_pct=min_change_pct,
            max_change_pct=max_change_pct,
            volume_ratio_min=volume_ratio_min,
            window_start_minutes=window_start_minutes,
            window_end_minutes=window_end_minutes,
        )
        if hit is not None:
            if phase == "partial":
                partial_warnings = list(hit.warnings)
                partial_warnings.append("分 K 盘中评估（窗口内实时触发）")
                return IntradayBreakoutSnapshot(
                    eligible=hit.eligible,
                    entry_price=hit.entry_price,
                    trigger_time=hit.trigger_time,
                    change_pct=hit.change_pct,
                    volume_ratio=hit.volume_ratio,
                    breakout_level=hit.breakout_level,
                    reasons=hit.reasons,
                    warnings=tuple(partial_warnings),
                )
            return hit

    last_change = _bar_change_pct(session_bars[-1], prev_close=prev_close)
    return IntradayBreakoutSnapshot(
        eligible=False,
        entry_price=0.0,
        trigger_time="",
        change_pct=last_change,
        volume_ratio=_minute_volume_ratio(session_bars, len(session_bars) - 1),
        breakout_level=_morning_high(session_bars, len(session_bars) - 1),
        reasons=empty.reasons,
        warnings=empty.warnings,
    )


def evaluate_intraday_breakout_from_local_minutes(
    vt_symbol: str,
    trade_date: date,
    *,
    min_change_pct: float = 3.0,
    max_change_pct: float = 7.0,
    volume_ratio_min: float = 1.2,
    window_start_minutes: int = DEFAULT_WINDOW_START_MINUTES,
    window_end_minutes: int = DEFAULT_WINDOW_END_MINUTES,
) -> IntradayBreakoutSnapshot | None:
    """本地 1m + 日 K 昨收评估；无分 K 数据时返回 None。"""
    bars = load_local_minute_bars_for_date(vt_symbol, trade_date)
    if not bars:
        return None
    symbol = vt_symbol.split(".", 1)[0]
    prev_close = resolve_prev_close_for_date(vt_symbol, trade_date)
    if prev_close <= 0:
        return None
    return evaluate_intraday_breakout_intraday(
        bars,
        prev_close=prev_close,
        symbol=symbol,
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        volume_ratio_min=volume_ratio_min,
        window_start_minutes=window_start_minutes,
        window_end_minutes=window_end_minutes,
        phase="closed",
    )
