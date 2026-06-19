"""信号区 + 持仓：关注池标的集合。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.config.preferences.watchlist_signal import load_signal_panel_symbols
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.storage.repositories.positions import load_position_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows

__all__ = [
    "load_focus_pool_stock_items",
    "stock_items_from_vt_symbols",
]


def _watchlist_name_map() -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for symbol, exchange, name in load_watchlist_rows():
        mapping[(symbol, exchange.name)] = name or ""
    return mapping


def _item_from_key(symbol: str, exchange_name: str, *, names: dict[tuple[str, str], str]) -> StockItem | None:
    parsed = parse_stock_symbol(f"{symbol}.{exchange_name}")
    if parsed is None:
        return None
    name = names.get((symbol, exchange_name), "") or parsed.name
    return StockItem(symbol=parsed.symbol, exchange=parsed.exchange, name=name)


def load_focus_pool_stock_items() -> list[StockItem]:
    """信号区名单 ∪ 持仓记账标的（去重，保序）。"""
    names = _watchlist_name_map()
    ordered_keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for vt_symbol in load_signal_panel_symbols():
        parsed = parse_stock_symbol(vt_symbol)
        if parsed is None:
            continue
        key = (parsed.symbol, parsed.exchange.name)
        if key in seen:
            continue
        seen.add(key)
        ordered_keys.append(key)

    for row in load_position_rows():
        symbol = str(row.get("symbol") or "").strip()
        exchange_name = str(row.get("exchange") or "").strip()
        if not symbol or not exchange_name:
            continue
        key = (symbol, exchange_name)
        if key in seen:
            continue
        seen.add(key)
        ordered_keys.append(key)

    items: list[StockItem] = []
    for symbol, exchange_name in ordered_keys:
        item = _item_from_key(symbol, exchange_name, names=names)
        if item is not None:
            items.append(item)
    return items


def stock_items_from_vt_symbols(vt_symbols: list[str] | tuple[str, ...]) -> list[StockItem]:
    names = _watchlist_name_map()
    items: list[StockItem] = []
    seen: set[tuple[str, Exchange]] = set()
    for vt_symbol in vt_symbols:
        text = str(vt_symbol or "").strip()
        if not text:
            continue
        parsed = parse_stock_symbol(text)
        if parsed is None:
            continue
        key = (parsed.symbol, parsed.exchange)
        if key in seen:
            continue
        seen.add(key)
        name = names.get((parsed.symbol, parsed.exchange.name), "") or parsed.name
        items.append(StockItem(symbol=parsed.symbol, exchange=parsed.exchange, name=name))
    return items
