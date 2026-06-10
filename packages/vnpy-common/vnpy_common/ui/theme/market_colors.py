"""A 股涨跌语义色（随 ThemeTokens 切换）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vnpy.trader.ui import QtGui

from vnpy_common.ui.theme.tokens import ThemeTokens


@dataclass(frozen=True)
class MarketColors:
    rise: str
    fall: str
    flat: str


class _QuoteLike(Protocol):
    is_rise: bool
    is_fall: bool


def market_colors(t: ThemeTokens) -> MarketColors:
    return MarketColors(rise=t.market_rise, fall=t.market_fall, flat=t.market_flat)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = QtGui.QColor(hex_color)
    return color.red(), color.green(), color.blue()


def market_rgb(t: ThemeTokens) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    colors = market_colors(t)
    return hex_to_rgb(colors.rise), hex_to_rgb(colors.fall)


def quote_change_color(quote: _QuoteLike, t: ThemeTokens) -> str:
    colors = market_colors(t)
    if quote.is_rise:
        return colors.rise
    if quote.is_fall:
        return colors.fall
    return colors.flat


def pct_change_color(value: float | None, t: ThemeTokens) -> str:
    colors = market_colors(t)
    if value is None:
        return colors.flat
    if value > 0:
        return colors.rise
    if value < 0:
        return colors.fall
    return colors.flat


def price_change_color(price: float, prev_close: float, t: ThemeTokens) -> str:
    colors = market_colors(t)
    if prev_close <= 0:
        return colors.flat
    if price > prev_close:
        return colors.rise
    if price < prev_close:
        return colors.fall
    return colors.flat
