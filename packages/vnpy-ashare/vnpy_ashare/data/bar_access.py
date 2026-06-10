"""K 线与 A 股列表数据访问门面（Service / Worker / UI 统一 import 路径）。

分层约定（详见 docs/coding-standards.md）::

    有 MainEngine  → BarService.load_bars / get_overview（经 engine_access）
    无 Engine      → 本模块 re-export（Worker、单元测试、manager fallback）
    下载 / 同步    → bars.py、universe.py（写操作，不经本门面）

禁止 UI 直接 ``from vnpy_ashare.data.bar_store import …`` 或 ``from vnpy_ashare.storage.app_db import …``。
"""

from __future__ import annotations

from vnpy_ashare.storage.app_db import (
    build_symbol_name_map,
    count_universe,
    load_universe_page,
    load_universe_rows,
    load_universe_slice,
    search_universe,
    universe_exists,
)
from vnpy_ashare.data.bar_store import (
    PeriodBarOverview,
    delete_scope_bars,
    get_period_overview,
    get_scope_overview,
    iter_bar_overviews,
    load_period_bars,
    load_scope_bars,
)

__all__ = [
    "PeriodBarOverview",
    "build_symbol_name_map",
    "delete_scope_bars",
    "get_period_overview",
    "get_scope_overview",
    "iter_bar_overviews",
    "load_period_bars",
    "load_scope_bars",
    "count_universe",
    "load_universe_page",
    "load_universe_rows",
    "load_universe_slice",
    "search_universe",
    "universe_exists",
]
