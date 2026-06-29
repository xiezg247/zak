"""信号区表格 Model 单元测试。"""

from __future__ import annotations

from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_ashare.ui.quotes.watchlist_signals.signal_panel_model import SignalPanelTableModel


def test_set_rows_with_symbols_and_lookup() -> None:
    model = SignalPanelTableModel()
    model.set_headers(["代码", ""])
    model.set_rows_with_symbols(
        ["600000.SSE", "000001.SZSE"],
        [
            [QuoteCell(text="600000"), QuoteCell(text="理由")],
            [QuoteCell(text="000001"), QuoteCell(text="理由")],
        ],
    )
    assert model.rowCount() == 2
    assert model.vt_symbol_at(0) == "600000.SSE"
    assert model.row_for_vt_symbol("000001.SZSE") == 1
    assert model.row_for_vt_symbol("missing") == -1


def test_apply_row_updates_without_reset() -> None:
    model = SignalPanelTableModel()
    model.set_headers(["信号"])
    model.set_rows_with_symbols(["600000.SSE"], [[QuoteCell(text="买")]])
    reset_calls: list[int] = []

    with patch.object(model, "beginResetModel", side_effect=lambda: reset_calls.append(1)):
        model.set_rows_with_symbols(["600000.SSE"], [[QuoteCell(text="卖")]])

    assert reset_calls == []
    index = model.index(0, 0)
    assert model.data(index) == "卖"
