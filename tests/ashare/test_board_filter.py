"""板块筛选测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.board import matches_board


class BoardFilterTests(unittest.TestCase):
    def test_matches_board_all(self) -> None:
        self.assertTrue(matches_board("600519", None))
        self.assertTrue(matches_board("300750", "全部"))

    def test_matches_board_main(self) -> None:
        self.assertTrue(matches_board("600519", "沪深主板"))
        self.assertFalse(matches_board("300750", "沪深主板"))

    def test_matches_board_chinext(self) -> None:
        self.assertTrue(matches_board("300750", "创业板"))
        self.assertFalse(matches_board("688981", "创业板"))


if __name__ == "__main__":
    unittest.main()
