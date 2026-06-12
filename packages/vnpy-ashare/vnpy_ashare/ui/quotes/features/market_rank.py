"""市场页榜单侧栏（rank catalog 选择与排序同步）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.quotes.rank_catalog import get_rank_definition, list_rank_definitions, rank_definition_index

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

RANK_SETTINGS_KEY = "quotes/market/active_rank_id_v1"


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
        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        saved = str(settings.value(RANK_SETTINGS_KEY, "") or "").strip()
        if saved:
            return get_rank_definition(saved).id
        return page.config.default_rank_id

    def save_rank_id_pref(self, rank_id: str) -> None:
        if not self._page.config.show_rank_sidebar:
            return
        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        settings.setValue(RANK_SETTINGS_KEY, rank_id)

    def sync_sort_from_catalog(self) -> None:
        page = self._page
        spec = get_rank_definition(page._market_rank_id)
        page._market_sort_column = spec.sort_column or spec.redis_field
        page._market_sort_ascending = spec.ascending

    def on_rank_type_changed(self, row: int) -> None:
        page = self._page
        if not page.config.show_rank_sidebar or row < 0:
            return

        specs = list_rank_definitions()
        if row >= len(specs):
            return
        spec = specs[row]
        if spec.id == page._market_rank_id:
            return
        page._market_rank_id = spec.id
        self.sync_sort_from_catalog()
        self.save_rank_id_pref(spec.id)
        page._market_page = 0
        page._market_page_cache.clear()
        page._market_catalog_loaded = False
        page._market_board_base = None
        page._market_board_base_key = None
        page._market_filter_keyword = ""
        page._market_loading_more = False
        page._market_last_load_more_at = 0.0
        page.load_stock_list()

    def init_sidebar_selection(self) -> None:
        page = self._page
        rank_list = getattr(page, "rank_list", None)
        if rank_list is None:
            return
        index = rank_definition_index(page._market_rank_id)
        rank_list.blockSignals(True)
        rank_list.setCurrentRow(index)
        rank_list.blockSignals(False)

    def active_rank_title(self) -> str:
        page = self._page
        if page.config.show_rank_sidebar:
            return get_rank_definition(page._market_rank_id).title
        return "涨幅榜"
