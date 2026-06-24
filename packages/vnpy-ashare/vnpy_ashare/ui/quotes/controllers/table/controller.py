"""行情表格控制器（组合各 mixin）。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase
from vnpy_ashare.ui.quotes.controllers.table.columns import TableColumnsMixin
from vnpy_ashare.ui.quotes.controllers.table.filter import TableFilterMixin
from vnpy_ashare.ui.quotes.controllers.table.market import TableMarketMixin
from vnpy_ashare.ui.quotes.controllers.table.refresh import TableRefreshMixin
from vnpy_ashare.ui.quotes.controllers.table.render import TableRenderMixin
from vnpy_ashare.ui.quotes.controllers.table.selection import TableSelectionMixin


class TableController(
    TableRefreshMixin,
    TableRenderMixin,
    TableSelectionMixin,
    TableMarketMixin,
    TableFilterMixin,
    TableColumnsMixin,
    TableControllerBase,
):
    """QuotesPage 表格与列配置。"""
