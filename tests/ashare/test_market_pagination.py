"""市场页分页可见性测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.pagination_controller import MarketPaginationController


class MarketPaginationVisibilityTests(unittest.TestCase):
    def _controller(self, *, auto_refresh: bool, market_full_list: bool = True) -> MarketPaginationController:
        page = SimpleNamespace(
            config=SimpleNamespace(
                use_market_rank=True,
                market_full_list=market_full_list,
                market_scroll_paging=False,
            ),
            market_auto_refresh_enabled=lambda: auto_refresh,
        )
        return MarketPaginationController(page)  # type: ignore[arg-type]

    def test_show_pagination_when_auto_refresh_on(self) -> None:
        controller = self._controller(auto_refresh=True)
        self.assertTrue(controller.should_show_pagination())

    def test_hide_pagination_when_snapshot_full_list(self) -> None:
        controller = self._controller(auto_refresh=False, market_full_list=True)
        self.assertFalse(controller.should_show_pagination())


if __name__ == "__main__":
    unittest.main()
