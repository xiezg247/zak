"""个股资金流序列加载测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.services.signals.stock_moneyflow_series import load_stock_moneyflow_values


class StockMoneyflowSeriesTests(unittest.TestCase):
    @mock.patch("vnpy_ashare.services.signals.stock_moneyflow_series.fetch_stock_moneyflow_series", return_value=[])
    @mock.patch("vnpy_ashare.services.signals.stock_moneyflow_series.get_cached_rows")
    @mock.patch(
        "vnpy_ashare.services.signals.stock_moneyflow_series.iter_trade_date_strs",
        return_value=[f"202406{i:02d}" for i in range(10, 22)],
    )
    def test_reads_from_local_cache(self, _dates: mock.Mock, cached_rows: mock.Mock, _fetch: mock.Mock) -> None:
        cached_rows.side_effect = [[{"ts_code": "600000.SH", "net_mf_amount": float(index)}] for index in range(12)]
        values = load_stock_moneyflow_values("600000.SSE", days=12)
        self.assertEqual(values, [float(index) for index in range(12)])

    @mock.patch("vnpy_ashare.services.signals.stock_moneyflow_series.fetch_stock_moneyflow_series")
    @mock.patch("vnpy_ashare.services.signals.stock_moneyflow_series.get_cached_rows", return_value=None)
    @mock.patch(
        "vnpy_ashare.services.signals.stock_moneyflow_series.iter_trade_date_strs",
        return_value=["20240620"],
    )
    def test_falls_back_to_api(self, _dates: mock.Mock, _cache: mock.Mock, fetch_series: mock.Mock) -> None:
        from vnpy_ashare.domain.stock.context import MoneyflowDayRow

        fetch_series.return_value = [
            MoneyflowDayRow(trade_date="20240618", net_mf_amount=10.0),
            MoneyflowDayRow(trade_date="20240619", net_mf_amount=20.0),
        ]
        values = load_stock_moneyflow_values("600000.SSE", days=15)
        self.assertEqual(values, [10.0, 20.0])


if __name__ == "__main__":
    unittest.main()
