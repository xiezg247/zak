"""format_quote_summary 纯函数测试。"""

from __future__ import annotations

import unittest

from tests.ashare.ai.context.factories import sample_quote
from vnpy_ashare.ai.context.quote.format import format_quote_summary


class TestFormatQuoteSummary(unittest.TestCase):
    def test_formats_price_and_change(self) -> None:
        text = format_quote_summary(sample_quote())
        self.assertIn("1500.00", text)
        self.assertIn("+0.67%", text)

    def test_empty_when_quote_missing(self) -> None:
        self.assertEqual(format_quote_summary(None), "")


if __name__ == "__main__":
    unittest.main()
