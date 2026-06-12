"""雷达页个人候选池（自选 / 信号区 / 持仓 / 选股）。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.config.preferences.watchlist_signal import load_signal_panel_symbols
from vnpy_ashare.domain.symbols import StockItem, parse_stock_symbol
from vnpy_ashare.screener.run.run_store import get_latest_run
from vnpy_ashare.storage.repositories.positions import load_position_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows

PERSONAL_POOL_MAX = 50
SCREENER_POOL_TOP = 15


def _vt_from_parts(symbol: str, exchange: Exchange | str) -> str:
    if isinstance(exchange, Exchange):
        return f"{symbol}.{exchange.value}"
    text = str(exchange or "").strip()
    if text in Exchange.__members__:
        return f"{symbol}.{Exchange[text].value}"
    return f"{symbol}.{text}"


def collect_personal_vt_symbols(*, max_items: int = PERSONAL_POOL_MAX) -> list[str]:
    """并集去重：自选 + 信号区 + 持仓。"""
    seen: set[str] = set()
    ordered: list[str] = []

    def add_vt(vt_symbol: str) -> None:
        text = str(vt_symbol or "").strip()
        if not text or text in seen:
            return
        if parse_stock_symbol(text) is None:
            return
        seen.add(text)
        ordered.append(text)

    for symbol, exchange, _name in load_watchlist_rows():
        add_vt(_vt_from_parts(symbol, exchange))

    for vt_symbol in load_signal_panel_symbols():
        add_vt(vt_symbol)

    for row in load_position_rows():
        add_vt(_vt_from_parts(str(row["symbol"]), str(row["exchange"])))

    return ordered[: max(1, int(max_items))]


def collect_horizon_candidates(*, max_items: int = 40) -> list[str]:
    """展望卡候选：个人池 + 最新选股 Top N。"""
    seen: set[str] = set()
    ordered: list[str] = []

    def add_vt(vt_symbol: str) -> None:
        text = str(vt_symbol or "").strip()
        if not text or text in seen:
            return
        if parse_stock_symbol(text) is None:
            return
        seen.add(text)
        ordered.append(text)

    for vt_symbol in collect_personal_vt_symbols(max_items=max_items):
        add_vt(vt_symbol)

    record = get_latest_run()
    if record is not None:
        for row in record.rows[:SCREENER_POOL_TOP]:
            add_vt(str(row.get("vt_symbol") or ""))
            if len(ordered) >= max_items:
                break

    return ordered[: max(1, int(max_items))]


def name_map_for_symbols(vt_symbols: list[str]) -> dict[str, str]:
    """vt_symbol → 名称。"""
    mapping: dict[str, str] = {}
    for symbol, exchange, name in load_watchlist_rows():
        mapping[_vt_from_parts(symbol, exchange)] = name
    for vt_symbol in vt_symbols:
        if vt_symbol in mapping and mapping[vt_symbol]:
            continue
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        if item.name:
            mapping[vt_symbol] = item.name
    return mapping


def stock_item_for_vt(vt_symbol: str) -> StockItem | None:
    return parse_stock_symbol(vt_symbol)
