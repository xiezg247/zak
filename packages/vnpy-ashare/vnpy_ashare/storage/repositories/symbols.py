"""证券代码与名称映射。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.universe import load_universe_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows


def build_symbol_name_map() -> dict[tuple[str, Exchange], str]:
    """证券代码 → 名称；优先 universe，自选池作补充。"""
    mapping: dict[tuple[str, Exchange], str] = {}
    for symbol, exchange, name in load_universe_rows():
        if name:
            mapping[(symbol, exchange)] = name
    for symbol, exchange, name in load_watchlist_rows():
        key = (symbol, exchange)
        if name and key not in mapping:
            mapping[key] = name
    return mapping
