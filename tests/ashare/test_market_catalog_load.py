"""市场页首屏分页与后台 catalog 加载测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.controllers.data_loader import DataLoaderController
from vnpy_ashare.ui.quotes.features.market_rank import MarketRankFeature


class MarketCatalogLoadTests(unittest.TestCase):
    def _page(self, *, auto_refresh: bool, catalog_loaded: bool = False) -> SimpleNamespace:
        table = SimpleNamespace(filter_market_display=MagicMock())
        pagination = SimpleNamespace(set_visible=MagicMock(), update_controls=MagicMock())
        return SimpleNamespace(
            _active=True,
            config=SimpleNamespace(
                use_market_rank=True,
                market_full_list=True,
                market_scroll_paging=False,
            ),
            _market_page=0,
            _market_full_load_quiet=True,
            _market_catalog_loaded=catalog_loaded,
            _market_rank_id="net_mf_in",
            _market_page_cache={},
            _market_board_base=None,
            _market_board_base_key=None,
            _market_loading_more=False,
            _market_last_load_more_at=0.0,
            _pending_industry_drilldown=None,
            _pending_concept_drilldown=None,
            _market_industry_filter=None,
            _market_vt_whitelist=None,
            _market_drilldown_label=None,
            _market_industry_filter_listener=None,
            _industry_map_cache=None,
            _table=table,
            _pagination=pagination,
            load_stock_list=MagicMock(),
            market_auto_refresh_enabled=lambda: auto_refresh,
            market_uses_client_pagination=lambda: catalog_loaded,
            _thread_active=MagicMock(return_value=False),
            _market_worker=None,
        )

    def test_load_stock_list_snapshot_uses_page_first(self) -> None:
        page = self._page(auto_refresh=False)
        loader = DataLoaderController(page)  # type: ignore[arg-type]
        loader.load_market_page = MagicMock()
        loader.load_market_full = MagicMock()

        loader.load_stock_list()

        page._pagination.set_visible.assert_called_once()
        self.assertTrue(page._market_full_load_quiet)
        loader.load_market_page.assert_called_once()
        loader.load_market_full.assert_not_called()

    def test_schedule_catalog_load_after_page_when_not_loaded(self) -> None:
        page = self._page(auto_refresh=False)
        loader = DataLoaderController(page)  # type: ignore[arg-type]
        loader.load_market_full = MagicMock()

        loader._schedule_market_catalog_load()

        loader.load_market_full.assert_called_once_with(quiet=True)

    def test_schedule_catalog_load_skips_when_catalog_ready(self) -> None:
        page = self._page(auto_refresh=False, catalog_loaded=True)
        loader = DataLoaderController(page)  # type: ignore[arg-type]
        loader.load_market_full = MagicMock()

        loader._schedule_market_catalog_load()

        loader.load_market_full.assert_not_called()

    def test_load_market_page_applies_pending_industry_when_catalog_ready(self) -> None:
        page = self._page(auto_refresh=False, catalog_loaded=True)
        page._pending_industry_drilldown = "工业金属"
        listener = MagicMock()
        page._market_industry_filter_listener = listener
        page._apply_pending_market_drilldown = MagicMock(return_value=True)
        loader = DataLoaderController(page)  # type: ignore[arg-type]

        loader.load_market_page()

        page._apply_pending_market_drilldown.assert_called_once()
        page._table.filter_market_display.assert_called_once()

    def test_apply_rank_drilldown_reuses_catalog_when_same_rank(self) -> None:
        page = self._page(auto_refresh=False, catalog_loaded=True)
        page._pending_industry_drilldown = "工业金属"
        page._apply_pending_market_drilldown = MagicMock(return_value=True)
        feature = MarketRankFeature.__new__(MarketRankFeature)
        feature._page = page

        feature.apply_rank_for_drilldown("net_mf_in")

        page._apply_pending_market_drilldown.assert_called_once()
        page._table.filter_market_display.assert_called_once()
        page.load_stock_list.assert_not_called()
        self.assertTrue(page._market_catalog_loaded)


if __name__ == "__main__":
    unittest.main()
