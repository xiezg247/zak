"""极致短线主池过滤测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.run.ultra_short_pool_filter import filter_ultra_short_main_pool


def _row(**kwargs) -> ScreenerResultRow:
    quote_fields = {
        "vt_symbol": "600519.SSE",
        "symbol": "600519",
        "name": "贵州茅台",
        "amount": 80_000_000.0,
        "total_mv": 500_000.0,
        "change_pct": 10.0,
        "limit_times": 2,
    }
    quote_fields.update({k: v for k, v in kwargs.items() if k in QuoteRow.model_fields})
    tags = {k: str(v) for k, v in kwargs.items() if k not in QuoteRow.model_fields}
    return ScreenerResultRow(quote=QuoteRow(**quote_fields), tags=tags)


class UltraShortPoolFilterTest(unittest.TestCase):
    def test_keeps_limit_up_row(self) -> None:
        filtered = filter_ultra_short_main_pool([_row()])
        self.assertEqual(len(filtered), 1)

    def test_drops_low_change_without_boards(self) -> None:
        row = _row(change_pct=1.0, limit_times=0)
        self.assertEqual(filter_ultra_short_main_pool([row]), [])


if __name__ == "__main__":
    unittest.main()
