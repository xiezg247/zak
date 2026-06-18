"""WatchlistHost / WatchlistPoolHost 协议测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist.pool_host import WatchlistPoolHost


class WatchlistPoolHostProtocolTests(unittest.TestCase):
    def test_declares_pool_capabilities(self) -> None:
        names = set(getattr(WatchlistPoolHost, "__annotations__", {}))
        self.assertIn("watchlist_pool_stocks", names)
        self.assertIn("add_watchlist_button", names)
        self.assertIn("_signals", names)
        self.assertIn("apply_filter", WatchlistPoolHost.__dict__)
        self.assertIn("_update_action_buttons", WatchlistPoolHost.__dict__)


class WatchlistHostProtocolTests(unittest.TestCase):
    def test_extends_pool_host(self) -> None:
        self.assertIn(WatchlistPoolHost, WatchlistHost.__mro__)
        host_only = set(getattr(WatchlistHost, "__annotations__", {}))
        self.assertIn("signal_cache", host_only)
        self.assertNotIn("add_watchlist_button", host_only)

    def test_declares_watchlist_page_capabilities(self) -> None:
        names = set(getattr(WatchlistHost, "__annotations__", {}))
        self.assertIn("signal_cache", names)
        self.assertIn("market_table", names)
        self.assertIn("display_stocks", names)
        self.assertIn("multiview_board", names)
        self.assertIn("find_stock_item", WatchlistHost.__dict__)
        self.assertIn("_wire_multiview", WatchlistHost.__dict__)
        self.assertIn("_wire_signal_panel", WatchlistHost.__dict__)
        self.assertIn("_wire_position_panel", WatchlistHost.__dict__)
        self.assertIn("apply_strategy_profile", WatchlistHost.__dict__)


if __name__ == "__main__":
    unittest.main()
