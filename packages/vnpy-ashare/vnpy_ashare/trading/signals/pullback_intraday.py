"""分 K 低吸评估（14:30 后承接 + 回踩 MA5 / 日内 −3%~−5%）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from vnpy_ashare.data.bar_store import load_scope_bars
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.limit_board_intraday import load_local_minute_bars_for_date

SessionPhase = Literal["partial", "closed"]

DEFAULT_WINDOW_START_MINUTES = 870  # 14:30
DEFAULT_WINDOW_END_MINUTES = 900  # 15:00
DEFAULT_MIN_DIP_PCT = -5.0
DEFAULT_MAX_DIP_PCT = -3.0


@dataclass(frozen=True)
class PullbackIntradaySnapshot:
    eligible: bool
    entry_price: float
    trigger_time: str
    change_pct: float
    daily_ma5: float
    near_ma5: bool
    dip_zone: bool
    volume_shrink: bool
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


def _bar_change_pct(bar: _MinuteBarLike, *, prev_close: float) -> float:
    if prev_close <= 0:
        return 0.0
    return (float(bar.close_price) - prev_close) / prev_close * 100


def _volume_shrink(bars: list[_MinuteBarLike], index: int) -> bool:
    bar = bars[index]
    minutes = _bar_clock_minutes(bar)
    if minutes is None:
        return True
    morning = [item for item in bars[:index] if (_bar_clock_minutes(item) or 0) < DEFAULT_WINDOW_START_MINUTES]
    if not morning:
        return True
    morning_avg = sum(float(item.volume) for item in morning) / len(morning)
    if morning_avg <= 0:
        return True
    return float(bar.volume) <= morning_avg


def resolve_daily_mas_for_date(
    vt_symbol: str,
    trade_date: date,
    *,
    ma_window: int = 5,
) -> tuple[float | None, float | None, float]:
    """trade_date 当日分 K 评估用的日 K MA5/MA10 与昨收（不含当日未收盘）。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None, None, 0.0
    start = datetime.combine(trade_date - timedelta(days=40), time(0, 0), tzinfo=CHINA_TZ)
    end = datetime.combine(trade_date, time(0, 0), tzinfo=CHINA_TZ)
    daily = load_scope_bars(item.symbol, item.exchange, "daily", start, end)
    prior = [row for row in daily if row.datetime.date() < trade_date]
    if len(prior) < ma_window:
        return None, None, 0.0
    closes = [float(row.close_price) for row in prior]
    prev_close = closes[-1]
    ma5 = sum(closes[-ma_window:]) / ma_window
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
    return ma5, ma10, prev_close


def _evaluate_bar(
    bars: list[_MinuteBarLike],
    index: int,
    *,
    prev_close: float,
    daily_ma5: float,
    daily_ma10: float | None,
    pullback_band_pct: float,
    min_dip_pct: float,
    max_dip_pct: float,
    window_start_minutes: int,
    window_end_minutes: int,
) -> PullbackIntradaySnapshot | None:
    bar = bars[index]
    if not _bar_in_window(
        bar,
        window_start_minutes=window_start_minutes,
        window_end_minutes=window_end_minutes,
    ):
        return None

    change_pct = _bar_change_pct(bar, prev_close=prev_close)
    band = pullback_band_pct / 100.0
    close = float(bar.close_price)
    near_ma5 = daily_ma5 > 0 and abs(close - daily_ma5) / daily_ma5 <= band
    dip_zone = min_dip_pct <= change_pct <= max_dip_pct
    trend_ok = daily_ma10 is None or daily_ma5 >= daily_ma10 * 0.995
    volume_shrink = _volume_shrink(bars, index)

    if not trend_ok or not volume_shrink or not (near_ma5 or dip_zone):
        return None

    trigger_time = _format_trigger_time(bar)
    reasons: list[str] = []
    if dip_zone:
        reasons.append(f"日内回调 {change_pct:.1f}%（承接 {min_dip_pct:.0f}~{max_dip_pct:.0f}%）")
    if near_ma5:
        reasons.append(f"贴近日 K MA5 {daily_ma5:.2f}")
    if volume_shrink:
        reasons.append("午后缩量承接")
    if trigger_time:
        reasons.append(f"触发 {trigger_time[:2]}:{trigger_time[2:4]}")

    return PullbackIntradaySnapshot(
        eligible=True,
        entry_price=close,
        trigger_time=trigger_time,
        change_pct=change_pct,
        daily_ma5=daily_ma5,
        near_ma5=near_ma5,
        dip_zone=dip_zone,
        volume_shrink=volume_shrink,
        reasons=tuple(reasons),
        warnings=("分 K 规则（14:30 后承接）",),
    )


def evaluate_pullback_intraday(
    bars: list[_MinuteBarLike],
    *,
    prev_close: float,
    daily_ma5: float,
    daily_ma10: float | None = None,
    pullback_band_pct: float = 2.0,
    min_dip_pct: float = DEFAULT_MIN_DIP_PCT,
    max_dip_pct: float = DEFAULT_MAX_DIP_PCT,
    window_start_minutes: int = DEFAULT_WINDOW_START_MINUTES,
    window_end_minutes: int = DEFAULT_WINDOW_END_MINUTES,
    phase: SessionPhase = "closed",
) -> PullbackIntradaySnapshot:
    session_bars = _session_minute_bars(bars)
    empty = PullbackIntradaySnapshot(
        eligible=False,
        entry_price=0.0,
        trigger_time="",
        change_pct=0.0,
        daily_ma5=daily_ma5,
        near_ma5=False,
        dip_zone=False,
        volume_shrink=False,
        reasons=("未满足低吸条件",),
        warnings=("分 K 规则（14:30 后承接）",) if session_bars else ("无有效分 K",),
    )

    if prev_close <= 0 or daily_ma5 <= 0 or not session_bars:
        return empty

    for index in range(len(session_bars)):
        hit = _evaluate_bar(
            session_bars,
            index,
            prev_close=prev_close,
            daily_ma5=daily_ma5,
            daily_ma10=daily_ma10,
            pullback_band_pct=pullback_band_pct,
            min_dip_pct=min_dip_pct,
            max_dip_pct=max_dip_pct,
            window_start_minutes=window_start_minutes,
            window_end_minutes=window_end_minutes,
        )
        if hit is not None:
            if phase == "partial":
                partial_warnings = list(hit.warnings)
                partial_warnings.append("分 K 盘中评估（午后窗口）")
                return PullbackIntradaySnapshot(
                    eligible=hit.eligible,
                    entry_price=hit.entry_price,
                    trigger_time=hit.trigger_time,
                    change_pct=hit.change_pct,
                    daily_ma5=hit.daily_ma5,
                    near_ma5=hit.near_ma5,
                    dip_zone=hit.dip_zone,
                    volume_shrink=hit.volume_shrink,
                    reasons=hit.reasons,
                    warnings=tuple(partial_warnings),
                )
            return hit

    last_change = _bar_change_pct(session_bars[-1], prev_close=prev_close)
    return PullbackIntradaySnapshot(
        eligible=False,
        entry_price=0.0,
        trigger_time="",
        change_pct=last_change,
        daily_ma5=daily_ma5,
        near_ma5=False,
        dip_zone=False,
        volume_shrink=False,
        reasons=empty.reasons,
        warnings=empty.warnings,
    )


def evaluate_pullback_from_local_minutes(
    vt_symbol: str,
    trade_date: date,
    *,
    ma_window: int = 5,
    pullback_band_pct: float = 2.0,
    min_dip_pct: float = DEFAULT_MIN_DIP_PCT,
    max_dip_pct: float = DEFAULT_MAX_DIP_PCT,
    window_start_minutes: int = DEFAULT_WINDOW_START_MINUTES,
    window_end_minutes: int = DEFAULT_WINDOW_END_MINUTES,
) -> PullbackIntradaySnapshot | None:
    bars = load_local_minute_bars_for_date(vt_symbol, trade_date)
    if not bars:
        return None
    ma5, ma10, prev_close = resolve_daily_mas_for_date(vt_symbol, trade_date, ma_window=ma_window)
    if ma5 is None or prev_close <= 0:
        return None
    return evaluate_pullback_intraday(
        bars,
        prev_close=prev_close,
        daily_ma5=ma5,
        daily_ma10=ma10,
        pullback_band_pct=pullback_band_pct,
        min_dip_pct=min_dip_pct,
        max_dip_pct=max_dip_pct,
        window_start_minutes=window_start_minutes,
        window_end_minutes=window_end_minutes,
        phase="closed",
    )
