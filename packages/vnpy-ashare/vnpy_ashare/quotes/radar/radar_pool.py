"""雷达页个人候选池（自选 / 信号区 / 持仓 / 选股）。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.config.constants.watchlist import SHORT_TERM_FOCUS_GROUP_NAME
from vnpy_ashare.config.preferences.watchlist_signal import load_signal_panel_symbols
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.storage.repositories.positions import load_position_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows
from vnpy_ashare.storage.repositories.watchlist_groups import load_watchlist_group_member_keys, load_watchlist_groups

PERSONAL_POOL_MAX = 50


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


def collect_short_term_focus_vt_symbols(*, max_items: int = 30) -> list[str]:
    """「短线关注」分组成分（无分组时返回空）。"""
    group_id: str | None = None
    for group in load_watchlist_groups():
        if group.name == SHORT_TERM_FOCUS_GROUP_NAME:
            group_id = group.id
            break
    if not group_id:
        return []

    ordered: list[str] = []
    seen: set[str] = set()
    for symbol, exchange in load_watchlist_group_member_keys(group_id):
        vt_symbol = _vt_from_parts(symbol, exchange)
        if vt_symbol in seen or parse_stock_symbol(vt_symbol) is None:
            continue
        seen.add(vt_symbol)
        ordered.append(vt_symbol)
    return ordered[: max(1, int(max_items))]


def collect_outlook_exclusion_vt_symbols() -> set[str]:
    """未来展望扫描排除集：自选 + 信号区 + 持仓（已在自选页覆盖）。"""
    result: set[str] = set()
    for symbol, exchange, _name in load_watchlist_rows():
        result.add(_vt_from_parts(symbol, exchange))
    for vt_symbol in load_signal_panel_symbols():
        text = str(vt_symbol or "").strip()
        if text:
            result.add(text)
    for row in load_position_rows():
        result.add(_vt_from_parts(str(row["symbol"]), str(row["exchange"])))
    return result


def name_map_for_symbols(vt_symbols: list[str]) -> dict[str, str]:
    """vt_symbol → 名称（仅自选池与 StockItem 已有字段，不查 universe 全表）。"""
    watchlist_names = {
        _vt_from_parts(symbol, exchange): name
        for symbol, exchange, name in load_watchlist_rows()
        if str(name or "").strip()
    }
    mapping: dict[str, str] = {}
    for vt_symbol in vt_symbols:
        text = str(vt_symbol or "").strip()
        if not text:
            continue
        watchlist_name = watchlist_names.get(text, "")
        if watchlist_name:
            mapping[text] = watchlist_name
            continue
        item = parse_stock_symbol(text)
        if item is not None and item.name:
            mapping[text] = item.name
    return mapping


def stock_item_for_vt(vt_symbol: str) -> StockItem | None:
    return parse_stock_symbol(vt_symbol)
