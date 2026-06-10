"""A 股板块筛选（与 universe SQL 规则一致）。"""

from __future__ import annotations


def matches_board(symbol: str, board: str | None) -> bool:
    """证券代码是否属于指定板块；``board`` 为 None 或「全部」时恒为 True。"""
    if not board or board == "全部":
        return True
    if board == "沪深主板":
        prefixes = ("600", "601", "603", "000", "001", "002", "003")
        return symbol.startswith(prefixes)
    if board == "创业板":
        return symbol.startswith("300")
    if board == "科创板":
        return symbol.startswith("688")
    if board == "北交所":
        return symbol.startswith(("8", "4"))
    return True
