"""市场页首屏分页与后台 catalog 加载测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.controllers.data_loader import DataLoaderController


class MarketCatalogLoadTests(unittest.TestCase):
    def _page(self, *, auto_refresh: bool, catalog_loaded: bool = False) -> SimpleNamespace:
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
            _pagination=SimpleNamespace(set_visible=MagicMock()),
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


if __name__ == "__main__":
    unittest.main()
