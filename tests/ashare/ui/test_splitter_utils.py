"""splitter_utils 单元测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.components.splitter_utils import clamp_primary_sizes


class SplitterUtilsTests(unittest.TestCase):
    def test_clamp_primary_sizes_fills_shortfall(self) -> None:
        result = clamp_primary_sizes([500, 200], total=800, primary_min=160)
        self.assertEqual(sum(result), 800)
        self.assertGreaterEqual(result[0], 160)

    def test_clamp_primary_sizes_shrinks_overflow(self) -> None:
        result = clamp_primary_sizes([700, 300], total=800, primary_min=160)
        self.assertEqual(sum(result), 800)
        self.assertEqual(result[1], 300)


if __name__ == "__main__":
    unittest.main()
