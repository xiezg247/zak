"""封板时间工具测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.trading.signals.seal_time import format_seal_time_label, seal_before_cutoff, seal_time_score


class SealTimeTests(unittest.TestCase):
    def test_score_buckets(self) -> None:
        self.assertEqual(seal_time_score("09:35:00"), 1.0)
        self.assertEqual(seal_time_score("11:00:00"), 0.7)
        self.assertEqual(seal_time_score("14:20:00"), 0.5)

    def test_format_label(self) -> None:
        self.assertEqual(format_seal_time_label("103015"), "10:30 封板")

    def test_cutoff(self) -> None:
        self.assertTrue(seal_before_cutoff("10:00:00"))
        self.assertFalse(seal_before_cutoff("14:00:00"))
