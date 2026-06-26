"""持仓区表格 Model（QAbstractTableModel）。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.table.vt_symbol_panel_model import VtSymbolPanelTableModel


class PositionPanelTableModel(VtSymbolPanelTableModel):
    """持仓区行数据；每行额外绑定 vt_symbol。"""
