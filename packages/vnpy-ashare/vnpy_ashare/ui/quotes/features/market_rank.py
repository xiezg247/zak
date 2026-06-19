"""市场页榜单侧栏（rank catalog 选择与排序同步）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.quotes.rank.rank_catalog import DEFAULT_RANK_ID, get_rank_definition, rank_definition_row
from vnpy_ashare.ui.quotes.features.market_rank_sidebar import rank_id_from_sidebar_row

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

RANK_SETTINGS_KEY = "quotes/market/active_rank_id_v1"
SECTOR_DRILLDOWN_RANK_ID = "net_mf_in"


class MarketRankFeature:
    """封装 QuotesPage 市场榜侧栏逻辑。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        page._market_rank_id = self.load_rank_id_pref()
        self.sync_sort_from_catalog()

    def load_rank_id_pref(self) -> str:
        page = self._page
        if not page.config.show_rank_sidebar:
            return page.config.default_rank_id
        settings = get_settings()
        saved = str(settings.value(RANK_SETTINGS_KEY, "") or "").strip()
        if saved:
            return get_rank_definition(saved).id
        return page.config.default_rank_id

    def save_rank_id_pref(self, rank_id: str) -> None:
        if not self._page.config.show_rank_sidebar:
            return
        settings = get_settings()
        settings.setValue(RANK_SETTINGS_KEY, rank_id)

    def sync_sort_from_catalog(self) -> None:
        page = self._page
        spec = get_rank_definition(page._market_rank_id)
        page._market_sort_column = spec.sort_column or spec.redis_field
        page._market_sort_ascending = spec.ascending

    def on_rank_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        """单击切换榜单；再次点击当前榜单则恢复默认涨幅榜。"""
        page = self._page
        if not page.config.show_rank_sidebar:
            return
        rank_list = getattr(page, "rank_list", None)
        if rank_list is None:
            return
        row = rank_list.row(item)
        rank_id = rank_id_from_sidebar_row(rank_list, row)
        if not rank_id:
            return
        if rank_id == page._market_rank_id:
            if rank_id == DEFAULT_RANK_ID:
                return
            self._switch_rank(DEFAULT_RANK_ID)
            return
        self._switch_rank(rank_id)

    def _switch_rank(self, rank_id: str) -> None:
        page = self._page
        page._market_rank_id = rank_id
        self.sync_sort_from_catalog()
        self.save_rank_id_pref(rank_id)
        page._market_page = 0
        page._market_page_cache.clear()
        page._market_catalog_loaded = False
        page._market_board_base = None
        page._market_board_base_key = None
        page._market_filter_keyword = ""
        page._market_loading_more = False
        page._market_last_load_more_at = 0.0
        self.init_sidebar_selection()
        page.load_stock_list()

    def init_sidebar_selection(self) -> None:
        page = self._page
        rank_list = getattr(page, "rank_list", None)
        if rank_list is None:
            return
        index = rank_definition_row(page._market_rank_id)
        rank_list.blockSignals(True)
        rank_list.setCurrentRow(index)
        rank_list.blockSignals(False)

    def active_rank_title(self) -> str:
        page = self._page
        if page.config.show_rank_sidebar:
            return get_rank_definition(page._market_rank_id).title
        return "涨幅榜"

    def apply_rank_for_drilldown(self, rank_id: str = SECTOR_DRILLDOWN_RANK_ID) -> None:
        """板块资金等下钻：切换榜单并重新加载全市场列表。"""
        page = self._page
        target = get_rank_definition(rank_id).id
        if target == page._market_rank_id:
            page._market_page = 0
            page._market_page_cache.clear()
            page._market_board_base = None
            page._market_board_base_key = None
            page._market_loading_more = False
            page._market_last_load_more_at = 0.0
            if page._market_catalog_loaded and page.config.market_full_list:
                if page._apply_pending_market_drilldown():
                    page._table.filter_market_display()
                    page._pagination.update_controls()
                return
            page._market_catalog_loaded = False
            page.load_stock_list()
            return
        row = rank_definition_row(target)
        rank_list = getattr(page, "rank_list", None)
        if rank_list is not None:
            item = rank_list.item(row)
            if item is not None:
                self.on_rank_item_clicked(item)
                return
        self._switch_rank(target)
