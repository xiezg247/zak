"""AI 上下文测试数据工厂。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import StockBinding
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot

# mock.patch 目标：assembly 内 `from repo import fn` 绑定，须 patch 使用处而非 repository 模块。
WATCHLIST_ROWS = "vnpy_ashare.ai.context.quote.assembly.load_watchlist_rows"
POSITION_CONTAINS = "vnpy_ashare.ai.context.quote.assembly.position_contains"
IS_IN_WATCHLIST = "vnpy_ashare.ai.context.quote.assembly.is_symbol_in_watchlist"


def maotai_item() -> StockItem:
    return StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")


def pudong_item() -> StockItem:
    return StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")


def maotai_binding() -> StockBinding:
    return StockBinding(
        symbol="600519",
        exchange_cn="上交所",
        name="贵州茅台",
        vt_symbol="600519.SSE",
    )


def iflytek_binding() -> StockBinding:
    return StockBinding(
        symbol="002230",
        exchange_cn="深交所",
        name="科大讯飞",
        vt_symbol="002230.SZSE",
    )


def maotai_quote(**overrides: float | str) -> QuoteSnapshot:
    data = {
        "symbol": "600519",
        "name": "贵州茅台",
        "last_price": 1688.0,
        "change_amount": 38.0,
        "change_pct": 2.3,
        "open_price": 1650.0,
        "high_price": 1695.0,
        "low_price": 1648.0,
        "prev_close": 1650.0,
        "turnover_rate": 0.5,
        "volume": 1_000_000.0,
    }
    data.update(overrides)
    return QuoteSnapshot(**data)


def sample_quote(**overrides: float | str) -> QuoteSnapshot:
    data = {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "last_price": 1500.0,
        "prev_close": 1490.0,
        "open_price": 1495.0,
        "high_price": 1510.0,
        "low_price": 1490.0,
        "change_amount": 10.0,
        "change_pct": 0.67,
        "turnover_rate": 0.5,
        "volume": 10000.0,
    }
    data.update(overrides)
    return QuoteSnapshot(**data)
