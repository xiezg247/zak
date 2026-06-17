"""行情时间格式化测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.time.quote_time import (
    format_batch_updated_at,
    format_trade_time_display,
    resolve_trade_time_from_tickflow_row,
)


class QuoteTimeTest(unittest.TestCase):
    def test_format_trade_time_display(self) -> None:
        self.assertEqual(
            format_trade_time_display("2026-06-05 15:00:02"),
            "2026-06-05 15:00:02",
        )
        self.assertEqual(
            format_trade_time_display("2026-06-06T23:46:38"),
            "2026-06-06 23:46:38",
        )
        self.assertEqual(format_trade_time_display(""), "—")

    def test_format_batch_updated_at(self) -> None:
        self.assertEqual(
            format_batch_updated_at("2026-06-06T23:46:38"),
            "06-06 23:46:38",
        )
        self.assertEqual(format_batch_updated_at(None), "")

    def test_resolve_trade_time_from_timestamp(self) -> None:
        resolved = resolve_trade_time_from_tickflow_row(
            {
                "symbol": "600519.SH",
                "timestamp": 1_739_123_400_000,
            }
        )
        self.assertTrue(resolved)


if __name__ == "__main__":
    unittest.main()
