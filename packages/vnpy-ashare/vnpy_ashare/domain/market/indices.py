"""主要市场指数代码（TickFlow / Tushare 共用）。"""

from __future__ import annotations

MARKET_INDICES: list[tuple[str, str]] = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
    ("000300.SH", "沪深300"),
    ("000905.SH", "中证500"),
    ("000016.SH", "上证50"),
    ("899050.BJ", "北证50"),
]

MARKET_INDEX_TS_CODES: tuple[str, ...] = tuple(code for code, _ in MARKET_INDICES)
