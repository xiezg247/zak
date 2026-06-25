"""持仓区表格 Model 单元测试。"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_ashare.ui.quotes.watchlist_positions.position_panel_model import PositionPanelTableModel


def test_position_model_vt_symbol_and_background() -> None:
    model = PositionPanelTableModel()
    model.set_headers(["代码", "浮盈"])
    model.set_rows_with_symbols(
        ["600000.SSE"],
        [[QuoteCell(text="600000", bg_color="#112233"), QuoteCell(text="+1.00", color="#ff0000")]],
    )
    assert model.rowCount() == 1
    assert model.row_for_vt_symbol("600000.SSE") == 0
    bg_index = model.index(0, 0)
    bg_value = model.data(bg_index, QtCore.Qt.ItemDataRole.BackgroundRole)
    assert bg_value is not None
