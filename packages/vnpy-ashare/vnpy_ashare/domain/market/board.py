"""A 股板块筛选（与 universe SQL 规则一致）。"""

from __future__ import annotations

# 板块 → 证券代码前缀（Python / Polars 共用，避免规则漂移）
BOARD_PREFIXES: dict[str, tuple[str, ...]] = {
    "沪深主板": ("600", "601", "603", "000", "001", "002", "003"),
    "创业板": ("300",),
    "科创板": ("688",),
    "北交所": ("8", "4"),
}


def matches_board(symbol: str, board: str | None) -> bool:
    """证券代码是否属于指定板块；``board`` 为 None 或「全部」时恒为 True。"""
    if not board or board == "全部":
        return True
    prefixes = BOARD_PREFIXES.get(board)
    if prefixes is None:
        return True
    return symbol.startswith(prefixes)
