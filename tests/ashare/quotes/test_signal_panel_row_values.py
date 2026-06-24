"""信号区行渲染测试。"""

from __future__ import annotations

from types import SimpleNamespace

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.watchlist_signals.table_view import (
    _compute_row_values,
    _resolve_signal_row_name,
)


def test_resolve_signal_row_name_prefers_quote() -> None:
    item = StockItem(symbol="600497", exchange=Exchange.SSE, name="")
    quote = SimpleNamespace(name="驰宏锌锗")
    assert _resolve_signal_row_name(item, quote) == "驰宏锌锗"


def test_resolve_signal_row_name_falls_back_to_item() -> None:
    item = StockItem(symbol="603993", exchange=Exchange.SSE, name="洛阳钼业")
    assert _resolve_signal_row_name(item, None) == "洛阳钼业"


def test_compute_row_values_uses_quote_name_when_item_name_missing() -> None:
    item = StockItem(symbol="002428", exchange=Exchange.SZSE, name="")
    quote = SimpleNamespace(name="云南锗业")
    values = _compute_row_values(
        item,
        None,
        quote,
        bar_end_date=None,
        config=SimpleNamespace(slow_window=20, fast_window=10),
        panel_columns=(("signal", "信号"),),
    )
    assert values["name"] == "云南锗业"
