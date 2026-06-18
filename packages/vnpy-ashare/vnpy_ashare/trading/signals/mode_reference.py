"""分 K 极致短线模式参考线（打板 / 半路 / 低吸）。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Literal, cast

from pydantic import Field
from strategies.registry import resolve_intraday_mode_kind as _resolve_intraday_mode_kind
from strategies.ultra_short_signals import calc_limit_price

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.intraday_breakout_intraday import (
    DEFAULT_WINDOW_END_MINUTES as BREAKOUT_WINDOW_END,
)
from vnpy_ashare.trading.signals.intraday_breakout_intraday import (
    DEFAULT_WINDOW_START_MINUTES as BREAKOUT_WINDOW_START,
)
from vnpy_ashare.trading.signals.limit_board_intraday import (
    load_local_minute_bars_for_date,
    resolve_prev_close_for_date,
)
from vnpy_ashare.trading.signals.pullback_intraday import (
    DEFAULT_MAX_DIP_PCT,
    DEFAULT_MIN_DIP_PCT,
    resolve_daily_mas_for_date,
)
from vnpy_common.domain.base import FrozenModel

IntradayModeKind = Literal["limit_board", "halfway", "pullback", "none"]

MODE_LIMIT_COLOR = "#ff5c5c"
MODE_SUPPORT_COLOR = "#3ddc84"
MODE_BAND_COLOR = "#3ddc8488"
MODE_MA_COLOR = "#5eb3ff"
MODE_DIP_COLOR = "#ffb02099"
MODE_MUTED_COLOR = "#888888"


class ModeReferenceLine(FrozenModel):
    key: str = Field(description="标识")
    label: str = Field(description="图例标签")
    price: float = Field(description="价格")
    color: str = Field(description="线条颜色")
    style: Literal["dash", "dot"] = Field(default="dash", description="线型")


def resolve_intraday_mode_kind(strategy_id: str | None) -> IntradayModeKind:
    return cast(IntradayModeKind, _resolve_intraday_mode_kind(strategy_id))


def _trade_date() -> date:
    return datetime.now(CHINA_TZ).date()


def _prev_close(vt_symbol: str, quote: QuoteSnapshot | None) -> float:
    if quote is not None and quote.prev_close > 0:
        return float(quote.prev_close)
    resolved = resolve_prev_close_for_date(vt_symbol, _trade_date())
    return resolved if resolved > 0 else 0.0


def _morning_high_from_minute_bars(bars: list[object]) -> float | None:
    if not bars:
        return None
    highs = [float(getattr(bar, "high_price", 0) or 0) for bar in bars]
    highs = [value for value in highs if value > 0]
    if not highs:
        return None
    return max(highs)


def build_intraday_mode_reference_lines(
    vt_symbol: str,
    quote: QuoteSnapshot | None,
    *,
    mode: IntradayModeKind,
    minute_bars: Sequence[object] | None = None,
) -> tuple[ModeReferenceLine, ...]:
    """按买点模式生成分 K 参考线。"""
    if mode == "none":
        return ()

    prev_close = _prev_close(vt_symbol, quote)
    if prev_close <= 0:
        return ()

    symbol = vt_symbol.split(".")[0]
    bars = list(minute_bars or [])
    if not bars:
        bars = load_local_minute_bars_for_date(vt_symbol, _trade_date())

    if mode == "limit_board":
        limit_price = calc_limit_price(prev_close, symbol=symbol)
        if limit_price <= 0:
            return ()
        return (
            ModeReferenceLine(key="limit_up", label="涨停价", price=limit_price, color=MODE_LIMIT_COLOR),
            ModeReferenceLine(key="prev_close", label="昨收", price=prev_close, color=MODE_MUTED_COLOR, style="dot"),
        )

    if mode == "halfway":
        band_low = prev_close * 1.03
        band_high = prev_close * 1.07
        breakout = _morning_high_from_minute_bars(bars)
        if breakout is None and quote is not None and quote.high_price > 0:
            breakout = float(quote.high_price)
        lines: list[ModeReferenceLine] = [
            ModeReferenceLine(key="halfway_low", label="半路 3%", price=band_low, color=MODE_BAND_COLOR, style="dot"),
            ModeReferenceLine(key="halfway_high", label="半路 7%", price=band_high, color=MODE_BAND_COLOR, style="dot"),
        ]
        if breakout is not None and breakout > 0:
            lines.insert(0, ModeReferenceLine(key="breakout", label="突破位", price=breakout, color=MODE_SUPPORT_COLOR))
        return tuple(lines)

    trade_date = _trade_date()
    ma5, _ma10, _ = resolve_daily_mas_for_date(vt_symbol, trade_date)
    dip_low = prev_close * (1 + DEFAULT_MIN_DIP_PCT / 100)
    dip_high = prev_close * (1 + DEFAULT_MAX_DIP_PCT / 100)
    lines = [
        ModeReferenceLine(key="dip_low", label="低吸 −5%", price=dip_low, color=MODE_DIP_COLOR, style="dot"),
        ModeReferenceLine(key="dip_high", label="低吸 −3%", price=dip_high, color=MODE_DIP_COLOR, style="dot"),
    ]
    if ma5 is not None and ma5 > 0:
        lines.insert(0, ModeReferenceLine(key="ma5", label="日K MA5", price=ma5, color=MODE_MA_COLOR))
    return tuple(lines)


def mode_reference_window_hint(mode: IntradayModeKind) -> str:
    if mode == "halfway":
        start_h, start_m = divmod(BREAKOUT_WINDOW_START, 60)
        end_h, end_m = divmod(BREAKOUT_WINDOW_END, 60)
        return f"半路窗口 {start_h:02d}:{start_m:02d}–{end_h:02d}:{end_m:02d}"
    if mode == "pullback":
        return "低吸窗口 14:30–15:00"
    if mode == "limit_board":
        return "打板触板参考（涨停价）"
    return ""
