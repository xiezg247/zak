"""信号区表格 Model（QAbstractTableModel）。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.table.vt_symbol_panel_model import VtSymbolPanelTableModel


class SignalPanelTableModel(VtSymbolPanelTableModel):
    """信号区行数据；每行额外绑定 vt_symbol。"""
