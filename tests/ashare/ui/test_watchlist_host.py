"""WatchlistHost 协议测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


class WatchlistHostProtocolTests(unittest.TestCase):
    def test_declares_core_capabilities(self) -> None:
        names = set(getattr(WatchlistHost, "__annotations__", {}))
        self.assertIn("signal_cache", names)
        self.assertIn("position_cache", names)
        self.assertIn("display_stocks", names)
        self.assertIn("multiview_board", names)
        self.assertIn("find_stock_item", WatchlistHost.__dict__)
        self.assertIn("apply_strategy_profile", WatchlistHost.__dict__)
        self.assertIn("watchlist_pool_stocks", names)
        self.assertIn("apply_filter", WatchlistHost.__dict__)
        self.assertIn("_update_action_buttons", WatchlistHost.__dict__)


if __name__ == "__main__":
    unittest.main()
