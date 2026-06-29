"""VtSymbol 面板 Model 增量同步测试。"""

from __future__ import annotations

from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_ashare.ui.quotes.table.vt_symbol_panel_model import VtSymbolPanelTableModel


def _cell(text: str) -> QuoteCell:
    return QuoteCell(text=text)


def test_set_rows_same_symbols_uses_apply_row() -> None:
    model = VtSymbolPanelTableModel()
    model.set_headers(["name"])
    model.set_rows_with_symbols(["600000.SH"], [[_cell("a")]])
    reset_calls: list[int] = []

    with patch.object(model, "beginResetModel", side_effect=lambda: reset_calls.append(1)):
        model.set_rows_with_symbols(["600000.SH"], [[_cell("b")]])

    assert reset_calls == []
    assert model.data(model.index(0, 0)) == "b"


def test_set_rows_add_symbol_without_reset() -> None:
    model = VtSymbolPanelTableModel()
    model.set_headers(["name"])
    model.set_rows_with_symbols(["600000.SH"], [[_cell("a")]])
    reset_calls: list[int] = []

    with patch.object(model, "beginResetModel", side_effect=lambda: reset_calls.append(1)):
        model.set_rows_with_symbols(
            ["600000.SH", "000001.SZ"],
            [[_cell("a")], [_cell("b")]],
        )

    assert reset_calls == []
    assert model.rowCount() == 2
    assert model.vt_symbol_at(1) == "000001.SZ"


def test_set_rows_remove_symbol_without_reset() -> None:
    model = VtSymbolPanelTableModel()
    model.set_headers(["name"])
    model.set_rows_with_symbols(
        ["600000.SH", "000001.SZ"],
        [[_cell("a")], [_cell("b")]],
    )
    reset_calls: list[int] = []

    with patch.object(model, "beginResetModel", side_effect=lambda: reset_calls.append(1)):
        model.set_rows_with_symbols(["000001.SZ"], [[_cell("b")]])

    assert reset_calls == []
    assert model.rowCount() == 1
    assert model.vt_symbol_at(0) == "000001.SZ"
